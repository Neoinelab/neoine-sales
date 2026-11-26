import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { resetMock } from '../../test/fake/default'
import { ApiError } from '../../shared/api/problem'
import { formatWon } from '../../shared/model/money'
import type { DealRow } from '../../shared/model/types'
import { seedVendorId } from '../../test/fixtures/vendors'
import { dealInput } from '../../test/fake/testing'
import { renderAt } from '../../test/mockApp'
import { USER_ID } from '../../test/fake/seed/ids'

/** 시드 날짜가 기준일 상대값이라 기준일을 고정한다(2026-10-15). */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const COLUMNS = ['commit', 'most_likely', 'best', 'pipeline'] as const

function cellText(count: number, amount: number): string {
  return count === 0 ? '—' : `${count}건 · ${formatWon(amount)}`
}

/** 화면 표의 행(rowheader 이름)에서 셀 6개(Commit/Most Likely/Best/Pipeline/Total/Won) 텍스트를 읽는다. */
function readRow(name: string | RegExp): string[] {
  const header = screen.getByRole('rowheader', { name })
  const tr = header.closest('tr')
  if (!tr) throw new Error('행을 찾지 못했습니다.')
  return within(tr)
    .getAllByRole('cell')
    .map((c) => c.textContent?.trim() ?? '')
}

async function ledger(query: { year: number; quarter?: 1 | 2 | 3 | 4; month?: number; vendorId?: number; ownerId?: number }): Promise<DealRow[]> {
  const { quarter, ...rest } = query
  const page = await gateway.deals.list({ ...rest, ...(quarter ? { quarters: [quarter] } : {}), limit: 200 })
  return page.items
}

function sumOf(deals: DealRow[], pick: (d: DealRow) => boolean): { count: number; amount: number } {
  const hit = deals.filter(pick)
  return { count: hit.length, amount: hit.reduce((s, d) => s + (d.revenueAmount ?? 0), 0) }
}

const OPEN = new Set(['pipeline', 'best', 'most_likely', 'commit'])

function expectedCells(deals: DealRow[]): string[] {
  const cols = COLUMNS.map((k) => sumOf(deals, (d) => d.forecastKey === k))
  const total = sumOf(deals, (d) => OPEN.has(d.forecastKey))
  const won = sumOf(deals, (d) => d.forecastKey === 'won')
  return [...cols, total, won].map((s) => cellText(s.count, s.amount))
}

describe('Forecast 요약 표', () => {
  // 테스트 코드: FC-049
  it('열 순서(Commit, Most Likely, Best, Pipeline, Total(Open), Won)와 담당자 버튼·합계 행을 보여 준다', async () => {
    // when: 2026년 Forecast 화면을 연다 (전제: 기본 시드 Deal)
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    // then: 머리글이 Open 열 역순·Total(Open)·Won이고 담당자 버튼과 합계 행이 있다
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers).toEqual(['담당자', 'Commit', 'Most Likely', 'Best', 'Pipeline', 'Total(Open)', 'Won'])
    expect(screen.getByRole('button', { name: '김영업' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '박영업' })).toBeInTheDocument()
  })

  // 테스트 코드: FC-050
  it('합계 행과 담당자 행의 모든 셀이 Deal 목록 원장 합과 같다 (Lost 제외)', async () => {
    // when: 2026년 Forecast 화면을 연다 (전제: 기본 시드 Deal)
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    // then: 합계 행과 담당자별 행의 셀이 같은 조건 Deal 목록의 합과 같다
    const deals = await ledger({ year: 2026 })
    expect(readRow('합계')).toEqual(expectedCells(deals))
    for (const owner of ['김영업', '박영업', '이영업', '정영업']) {
      const mine = deals.filter((d) => d.owner.name === owner)
      expect(readRow(owner)).toEqual(expectedCells(mine))
    }
  })

  // 테스트 코드: FC-050
  it('Total은 Open(Commit+Most Likely+Best+Pipeline) 합이고 Won·Lost를 포함하지 않는다', async () => {
    // when: 2026년 Forecast 화면을 연다 (전제: Won·Lost Deal이 있는 시드)
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    // then: Total 셀은 Open 합, Won 셀은 Won 합이고 Lost 열은 없다
    const deals = await ledger({ year: 2026 })
    const lost = deals.filter((d) => d.forecastKey === 'lost')
    const won = deals.filter((d) => d.forecastKey === 'won')
    expect(lost.length).toBeGreaterThan(0)
    expect(won.length).toBeGreaterThan(0)
    const cells = readRow('합계')
    const openSum = sumOf(deals, (d) => OPEN.has(d.forecastKey))
    expect(cells[4]).toBe(cellText(openSum.count, openSum.amount))
    expect(cells[5]).toBe(cellText(won.length, won.reduce((s, d) => s + (d.revenueAmount ?? 0), 0)))
    // Lost를 더했다면 건수가 달라진다.
    expect(openSum.count + won.length + lost.length).toBe(deals.length)
    expect(screen.queryByRole('columnheader', { name: 'Lost' })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-051
  it('Expected Close 12/31은 그 해 Q4, 1/1은 다음 해 Q1로 들어간다', async () => {
    // given: 2026 Q4 화면과 12/31·다음 해 1/1 Expected Close로 바꾼 Pipeline Deal 둘
    const { client, user } = await renderAt('/forecast?year=2026&quarter=4', { role: 'admin' })
    await screen.findByRole('rowheader', { name: '합계' })
    const find = async (keyword: string): Promise<DealRow> => {
      const hit = (await gateway.deals.list({ keyword })).items[0]
      if (!hit) throw new Error(`시드 Deal을 찾지 못했습니다: ${keyword}`)
      return hit
    }
    const dec = await find('누리통신 NGFW') // 이영업 Pipeline 650,000,000
    const jan = await find('푸른물류 SSO') // 이영업 Pipeline 180,000,000
    await gateway.deals.update(dec.code, { revenueDate: '2026-12-31' })
    await gateway.deals.update(jan.code, { revenueDate: '2027-01-01' })
    // when: 요약을 다시 읽는다
    await client.invalidateQueries()

    // then: 2026 Q4 표에는 12/31 Deal만 있다
    await waitFor(() => expect(readRow('이영업')[3]).toBe(cellText(1, (dec.revenueAmount ?? 0))))
    expect(readRow('이영업')[3]).toBe('1건 · 650,000,000')

    // when: 2027 Q1로 바꾼다
    await user.selectOptions(screen.getByLabelText('연도'), '2027')
    await user.selectOptions(screen.getByLabelText('Quarter'), '1')
    // then: 2027 Q1 표에는 1/1 Deal이 있다
    await waitFor(() => expect(readRow('이영업')[3]).toBe('1건 · 180,000,000'))
  })

  // 테스트 코드: FC-052
  it('연도·Quarter·Vendor를 걸어도 합계가 원장 합과 같다', async () => {
    // when: 2026 Q4와 Vendor Silverfort 조건으로 화면을 연다
    await renderAt(`/forecast?year=2026&quarter=4&vendor=${seedVendorId('Silverfort')}`)
    await screen.findByRole('rowheader', { name: '합계' })
    // then: 합계 행이 같은 조건 Deal 목록의 합과 같다
    const deals = await ledger({ year: 2026, quarter: 4, vendorId: seedVendorId('Silverfort') })
    expect(deals.length).toBeGreaterThan(0)
    expect(readRow('합계')).toEqual(expectedCells(deals))
  })

  // 테스트 코드: FC-053
  it('요약 카드는 기간의 Open 합계와 Won(별도)을 건수와 함께 보인다', async () => {
    // when: 2026 Q4 화면을 연다
    await renderAt('/forecast?year=2026&quarter=4')
    await screen.findByRole('rowheader', { name: '합계' })
    // then: 카드에 Open 건수·금액과 Won 건수·금액이 있다
    const deals = await ledger({ year: 2026, quarter: 4 })
    const open = sumOf(deals, (d) => OPEN.has(d.forecastKey))
    const won = sumOf(deals, (d) => d.forecastKey === 'won')
    const card = screen.getByRole('region', { name: '2026 Q4 요약' })
    expect(within(card).getByText(/Open 합계/)).toBeInTheDocument()
    expect(card).toHaveTextContent(`${open.count}건`)
    expect(card).toHaveTextContent(formatWon(open.amount))
    expect(within(card).getByText(/Won/)).toBeInTheDocument()
    expect(card).toHaveTextContent(`${won.count}건`)
    expect(card).toHaveTextContent(formatWon(won.amount))
  })

  // 테스트 코드: FC-053, FC-068
  it('카드 제목·표 캡션·담당자 요약에 원 단위를 보인다', async () => {
    // when: 2026 Q4 화면을 연다
    const { user } = await renderAt('/forecast?year=2026&quarter=4')
    await screen.findByRole('rowheader', { name: '합계' })
    // then: 카드 제목·표 캡션에 단위가 있고 셀은 단위 글자 없이 숫자만이다
    const card = screen.getByRole('region', { name: '2026 Q4 요약' })
    expect(within(card).getByRole('heading', { name: 'Open 합계(단위:원)' })).toBeVisible()
    expect(within(card).getByRole('heading', { name: 'Won (별도, 단위:원)' })).toBeVisible()
    expect(screen.getByText('셀 값: 건수 · 금액(단위:원)')).toBeVisible()
    const cells = readRow('합계')
    for (const cell of cells) expect(cell).not.toMatch(/원|\d[MB]\b/)

    // when: 담당자를 누른다
    await user.click(await screen.findByRole('button', { name: '김영업' }))
    // then: 담당자 영역에 Open 건수와 금액(단위:원)이 요약 행 값으로 보인다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    const all = await ledger({ year: 2026, quarter: 4, ownerId: USER_ID.kim })
    const notLost = all.filter((d) => d.forecastKey !== 'lost')
    await waitFor(() => expect(within(section).getAllByRole('link')).toHaveLength(notLost.length))
    const open = sumOf(notLost, (d) => OPEN.has(d.forecastKey))
    expect(section).toHaveTextContent(`Open ${open.count}건 · 금액(단위:원) ${formatWon(open.amount)}`)
  })

  // 테스트 코드: FC-054
  it('퇴사 담당자도 "(퇴사)" 이름으로 행에 나온다', async () => {
    // when: 퇴사자 Owner Deal이 있는 2027 Q1 화면을 연다
    await renderAt('/forecast?year=2027&quarter=1')
    // then: "강퇴사(퇴사)" 담당자 버튼이 있다
    expect(await screen.findByRole('button', { name: '강퇴사(퇴사)' })).toBeInTheDocument()
  })
})

describe('담당자 선택: 같은 화면 아래 Deal 목록', () => {
  // 테스트 코드: FC-067
  it('담당자를 누르면 아래에 그 담당자 Deal 목록이 열리고 Deal 상세 링크가 나온다', async () => {
    // given: 2026 화면에서 아직 선택하지 않은 담당자 버튼
    const { user, location } = await renderAt('/forecast?year=2026')
    const button = await screen.findByRole('button', { name: '김영업' })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('region', { name: /선택한 담당자/ })).not.toBeInTheDocument()

    // when: 담당자 버튼을 누른다
    await user.click(button)

    // then: 담당자 영역이 열리고 URL에 sel이 생기며 요약 표는 그대로, 열·링크가 문서와 같다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    expect(screen.getByRole('button', { name: '김영업' })).toHaveAttribute('aria-pressed', 'true')
    expect(location()).toContain(`sel=${USER_ID.kim}`)
    // 요약 표가 그대로 남아 있다(별도 화면 이동 없음).
    expect(location()).toContain('/forecast')
    expect(screen.getByRole('rowheader', { name: '합계' })).toBeInTheDocument()

    const heads = within(section)
      .getAllByRole('columnheader')
      .map((h) => h.textContent)
    expect(heads).toEqual(['Deal', 'Status', 'Forecast', '금액(단위:원)', 'Expected Close', 'Next Action'])

    const deals = (await ledger({ year: 2026, ownerId: USER_ID.kim })).filter((d) => d.forecastKey !== 'lost')
    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThanOrEqual(deals.length))
    const first = deals.find((d) => d.name === '한빛은행 ITDR 도입')
    expect(first).toBeDefined()
    expect(within(section).getByRole('link', { name: '한빛은행 ITDR 도입' })).toHaveAttribute('href', `/deals/${first?.code}`)
    expect(within(section).queryByRole('link', { name: '박영업' })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-068
  it('선택한 담당자의 목록 합계(Lost 제외)가 요약 표의 그 담당자 행과 같다', async () => {
    // when: 2026 화면에서 김영업을 누른다
    const { user } = await renderAt('/forecast?year=2026')
    await user.click(await screen.findByRole('button', { name: '김영업' }))
    // then: 목록 위 Open 요약이 요약 표 행의 Total과 같고 Lost Deal은 목록에 없다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    const all = await ledger({ year: 2026, ownerId: USER_ID.kim })
    const deals = all.filter((d) => d.forecastKey !== 'lost')
    await waitFor(() => expect(within(section).getAllByRole('link')).toHaveLength(deals.length))
    expect(deals.length).toBeLessThan(all.length) // Lost는 표에 없다
    const open = sumOf(deals, (d) => OPEN.has(d.forecastKey))
    expect(readRow('김영업')[4]).toBe(cellText(open.count, open.amount))
    expect(section).toHaveTextContent(`Open ${open.count}건`)
    expect(section).toHaveTextContent(formatWon(open.amount))
  })

  // 테스트 코드: FC-068
  it('Lost Deal은 목록에 없고 Lost 안내 문구도 없다', async () => {
    // when: 김영업이 선택된 2026 화면을 연다
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    // then: Lost Deal 링크와 Lost 안내 문구가 없다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    expect(await within(section).findByRole('link', { name: '한빛은행 ITDR 도입' })).toBeInTheDocument()
    expect(within(section).queryByRole('link', { name: '새론병원 SSO' })).not.toBeInTheDocument()
    expect(section).not.toHaveTextContent(/Lost \d+건/)
    expect(section).not.toHaveTextContent('합계에서 제외')
  })

  // 테스트 코드: FC-067
  it('선택 해제 버튼으로 목록을 닫으면 URL에서 선택이 사라진다', async () => {
    // given: 김영업이 선택된 화면
    const { user, location } = await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    // when: "선택 해제" 버튼을 누른다
    await user.click(screen.getByRole('button', { name: '선택 해제' }))
    // then: 담당자 영역이 닫히고 URL에 sel이 없다
    expect(screen.queryByRole('region', { name: /선택한 담당자/ })).not.toBeInTheDocument()
    expect(location()).not.toContain('sel=')
  })

  // 테스트 코드: FC-067
  it('같은 담당자 버튼을 다시 누르면 선택이 해제된다', async () => {
    // given: 김영업이 선택된 화면
    const { user } = await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    // when: 같은 담당자 버튼을 다시 누른다
    await user.click(screen.getByRole('button', { name: '김영업' }))
    // then: 담당자 영역이 닫힌다
    expect(screen.queryByRole('region', { name: /선택한 담당자/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-067
  it('담당자 상세로 가는 메뉴·링크는 없다', async () => {
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    // then: "담당자 상세" 링크가 없다
    expect(screen.queryByRole('link', { name: /담당자 상세/ })).not.toBeInTheDocument()
  })
})

describe('Vendor 필터는 등록 Vendor 목록(id)을 쓴다', () => {
  // 테스트 코드: FC-065
  it('Vendor 선택지는 등록 Vendor이고 값은 id, 표시는 이름이다', async () => {
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    // then: 선택지가 "전체"와 등록 Vendor 이름이고 값이 Vendor id다
    const vendor = screen.getByLabelText('Vendor')
    await within(vendor).findByRole('option', { name: 'Okta' })

    expect(within(vendor).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '전체', 'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    expect(within(vendor).getByRole('option', { name: 'Okta' })).toHaveValue(String(seedVendorId('Okta')))
  })

  // 테스트 코드: FC-069
  it('선택한 담당자의 Deal 목록 조회에 Vendor 조건을 보낸다', async () => {
    // given: Deal 목록 조회를 지켜보는 스파이
    const list = vi.spyOn(gateway.deals, 'list')
    // when: Vendor와 담당자가 선택된 화면을 연다
    await renderAt(`/forecast?year=2026&vendor=${seedVendorId('Silverfort')}&sel=${USER_ID.kim}`)

    await screen.findByRole('heading', { name: /선택한 담당자/ })

    // then: 목록 조회에 담당자·연도·Vendor id가 담긴다
    await waitFor(() =>
      expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, vendorId: seedVendorId('Silverfort') })),
    )
  })

  // 테스트 코드: FC-065
  it('URL의 Vendor가 등록 Vendor가 아니면(옛 이름 등) 전체로 보인다', async () => {
    // when: 옛 이름 vendor=Silverfort로 화면을 연다
    await renderAt('/forecast?year=2026&vendor=Silverfort')
    await screen.findByRole('rowheader', { name: '합계' })

    // then: Vendor 칸이 "전체"다
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('전체'))
  })
})

describe('필터와 URL 유지', () => {
  // 테스트 코드: FC-060
  it('URL의 연도·Quarter·담당자·Vendor가 필터 칸에 복원된다', async () => {
    // when: 연도·Quarter·담당자·Vendor가 담긴 URL로 화면을 연다
    await renderAt(`/forecast?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${seedVendorId('Silverfort')}`)
    await screen.findByRole('rowheader', { name: '합계' })
    // then: 필터 칸 값이 URL과 같고 다른 담당자 행은 없다
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(screen.getByLabelText('Quarter')).toHaveValue('4')
    expect(screen.getByLabelText('담당자')).toHaveValue(String(USER_ID.kim))
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveDisplayValue('Silverfort'))
    // 담당자 필터가 걸리면 다른 담당자 행은 없다.
    expect(screen.queryByRole('button', { name: '박영업' })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-060
  it('필터를 바꾸면 URL에 남고 새로 고침 없이 표가 바뀐다', async () => {
    // given: 2026 화면과 처음 합계 행
    const { user, location } = await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    const before = readRow('합계')

    // when: Quarter를 4로 바꾼다
    await user.selectOptions(screen.getByLabelText('Quarter'), '4')
    // then: URL에 quarter가 생기고 표가 바뀐다
    expect(location()).toContain('quarter=4')
    await waitFor(() => expect(readRow('합계')).not.toEqual(before))

    // when: Vendor를 고른다
    await within(await screen.findByLabelText('Vendor')).findByRole('option', { name: 'Silverfort' })
    await user.selectOptions(screen.getByLabelText('Vendor'), 'Silverfort')
    // then: URL에 vendor가 생긴다
    expect(location()).toContain(`vendor=${seedVendorId('Silverfort')}`)

    // when: 담당자를 고른다
    await user.selectOptions(screen.getByLabelText('담당자'), String(USER_ID.kim))
    // then: URL에 owner가 생긴다
    expect(location()).toContain(`owner=${USER_ID.kim}`)

    // when: Quarter를 "전체"로 되돌린다
    await user.selectOptions(screen.getByLabelText('Quarter'), '')
    // then: URL에서 quarter가 사라진다
    expect(location()).not.toContain('quarter=')
  })

  // 테스트 코드: FC-060
  it('연도를 바꾸면 URL의 year가 바뀐다', async () => {
    // given: 2026 화면
    const { user, location } = await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    // when: 연도를 2027로 바꾼다
    await user.selectOptions(screen.getByLabelText('연도'), '2027')
    // then: URL의 year가 2027이고 2027 요약이 열린다
    expect(location()).toContain('year=2027')
    await screen.findByRole('region', { name: /2027 .*요약/ })
  })

  // 테스트 코드: FC-048
  it('year가 없으면 앱 시계의 올해로 열린다', async () => {
    // when: year 없이 화면을 연다 (전제: 앱 시계 2026-10-15)
    await renderAt('/forecast')
    await screen.findByLabelText('연도')
    // then: 연도 칸이 올해 2026이다
    expect(screen.getByLabelText('연도')).toHaveValue('2026') // 앱 시계(NOW)의 올해
  })
})

describe('상태와 접근 권한', () => {
  // 테스트 코드: FC-055
  it('조건에 맞는 Deal이 없으면 빈 문구를 보여 준다', async () => {
    // when: Deal이 없는 2020년 화면을 연다
    await renderAt('/forecast?year=2020')
    // then: 빈 상태 문구가 보이고 요약 표는 없다
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('rowheader', { name: '합계' })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-055
  it('불러오는 동안 로딩 문구가 나온다', async () => {
    // given: 끝나지 않는 요약 조회
    vi.spyOn(gateway.forecast, 'summary').mockReturnValue(new Promise(() => undefined))
    // when: 화면을 연다
    await renderAt('/forecast?year=2026')
    // then: "불러오는 중" 상태 문구가 보이고 요약 표는 없다
    await waitFor(() => {
      const statuses = screen.getAllByRole('status')
      expect(statuses.some((s) => s.textContent?.includes('불러오는 중'))).toBe(true)
    })
    expect(screen.queryByRole('rowheader', { name: '합계' })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-056
  it('요약 조회가 실패하면 오류를 alert로 보여 준다', async () => {
    // given: 500으로 실패하는 요약 조회
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(
      new ApiError(500, { type: 'about:blank', title: '서버 오류', status: 500, detail: '요약을 불러오지 못했습니다.' }),
    )
    // when: 화면을 연다
    await renderAt('/forecast?year=2026')
    // then: 서버 문구가 배너로 보인다
    expect(await screen.findByRole('alert')).toHaveTextContent('요약을 불러오지 못했습니다.')
  })

  // 테스트 코드: FC-047
  it.each(['admin', 'sales', 'user'] as const)('%s 역할도 조회할 수 있고 쓰기 동작은 없다', async (role) => {
    // when: 해당 역할로 2026 화면을 연다
    await renderAt('/forecast?year=2026', { role })
    // then: 요약 표가 보이고 제목 "Forecast"가 있으며 등록·수정·삭제·저장 버튼은 없다
    expect(await screen.findByRole('rowheader', { name: '합계' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Forecast' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /등록|수정|삭제|저장/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /등록/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-059
  it('요약 표는 이름 있는 가로 스크롤 영역 안에 있다', async () => {
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')
    // then: "담당자별 Forecast" 표가 .fc-scroll 영역 안에 있다
    const table = await screen.findByRole('table', { name: /담당자별 Forecast/ })
    expect(table.closest('.fc-scroll')).not.toBeNull()
  })
})

/** 서버 문자열의 오프셋 벽시계(YYYY-MM-DD HH:mm). 브라우저 시간대로 바꾸지 않는다. */
function offsetStamp(iso: string): string {
  return `${iso.slice(0, 10)} ${iso.slice(11, 16)}`
}

describe('기준 시각', () => {
  // 테스트 코드: FC-058
  it('실시간 기준 문구는 서버 시각을 보인다', async () => {
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })

    // then: "기준: 지금(서버 시각)" 문구가 보인다
    const summary = await gateway.forecast.summary({ year: 2026 })
    expect(summary.basis).toBe('live')
    expect(screen.getByText(`기준: 지금(${offsetStamp(summary.asOf)})`)).toBeVisible()
  })

  // 테스트 코드: FC-058
  it('기준 문구는 서버 시각을 그 오프셋의 벽시계 그대로 보인다', async () => {
    // given: as_of가 -05:00 오프셋인 요약 응답
    const original = gateway.forecast.summary.bind(gateway.forecast)
    vi.spyOn(gateway.forecast, 'summary').mockImplementation(async (query) => ({ ...(await original(query)), asOf: '2026-10-23T23:30:00-05:00' }))

    // when: 화면을 연다
    await renderAt('/forecast?year=2026')

    // then: 오프셋 벽시계 그대로 "2026-10-23 23:30"이 보인다
    expect(await screen.findByText('기준: 지금(2026-10-23 23:30)')).toBeVisible()
  })

  // 테스트 코드: FC-058
  it('Deal이 없는 기간에도 기준 문구를 보인다', async () => {
    // when: Deal이 없는 2020년 화면을 연다
    await renderAt('/forecast?year=2020')

    // then: 기준 문구가 보인다
    expect(await screen.findByText(/^기준: 지금\(\d{4}-\d{2}-\d{2} \d{2}:\d{2}\)$/)).toBeVisible()
  })
})

describe('월 필터', () => {
  // 테스트 코드: FC-061
  it('월을 고르면 URL에 month가 생기고 Quarter가 지워진다', async () => {
    // given: 2026 Q4 화면
    const { user, location } = await renderAt('/forecast?year=2026&quarter=4')
    await screen.findByRole('rowheader', { name: '합계' })

    // when: 월을 11월로 고른다
    await user.selectOptions(screen.getByLabelText('월'), '11월')

    // then: URL에 month가 있고 quarter가 없으며 Quarter 칸이 "전체"다
    expect(location()).toContain('month=11')
    expect(location()).not.toContain('quarter=')
    expect(screen.getByLabelText('Quarter')).toHaveValue('')
  })

  // 테스트 코드: FC-061
  it('Quarter를 고르면 월이 지워진다', async () => {
    // given: 2026년 11월 화면
    const { user, location } = await renderAt('/forecast?year=2026&month=11')
    await screen.findByLabelText('월')

    // when: Quarter를 3으로 고른다
    await user.selectOptions(screen.getByLabelText('Quarter'), '3')

    // then: URL에 quarter가 있고 month가 없으며 월 칸이 "전체"다
    expect(location()).toContain('quarter=3')
    expect(location()).not.toContain('month=')
    expect(screen.getByLabelText('월')).toHaveValue('')
  })

  // 테스트 코드: FC-061
  it('월 칸은 "전체"와 1월~12월을 보인다', async () => {
    // when: 2026 화면을 연다
    await renderAt('/forecast?year=2026')
    await screen.findByLabelText('월')

    // then: 선택지가 전체, 1월~12월이다
    expect(within(screen.getByLabelText('월')).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '전체',
      ...Array.from({ length: 12 }, (_, i) => `${i + 1}월`),
    ])
  })

  // 테스트 코드: FC-061
  it('URL에 Quarter와 월이 함께 있으면 Quarter만 쓴다', async () => {
    // when: quarter=4&month=11인 URL로 화면을 연다
    await renderAt('/forecast?year=2026&quarter=4&month=11')
    await screen.findByLabelText('월')

    // then: Quarter 칸은 4, 월 칸은 "전체"다
    expect(screen.getByLabelText('Quarter')).toHaveValue('4')
    expect(screen.getByLabelText('월')).toHaveValue('')
  })

  // 테스트 코드: FC-061
  it('월을 고르면 그 달만 집계하고 카드 제목에 월을 쓴다', async () => {
    // given: 2028년 2월 화면과 2월 말·3월 초 Deal
    const { client } = await renderAt('/forecast?year=2028&month=2')
    await screen.findByLabelText('월')
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '2월 말', revenueDate: '2028-02-29', forecastKey: 'commit', revenueAmount: 2_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '3월 초', revenueDate: '2028-03-01', forecastKey: 'commit', revenueAmount: 5_000_000 }))
    // when: 요약을 다시 읽는다
    await client.invalidateQueries()

    // then: 2월 Deal만 집계되고 카드 제목이 "2028 2월 요약"이며 원장 합과 같다
    await waitFor(() => expect(readRow('합계')[0]).toBe(cellText(1, 2_000_000)))
    expect(screen.getByRole('region', { name: '2028 2월 요약' })).toBeVisible()
    const deals = await ledger({ year: 2028, month: 2 })
    expect(readRow('합계')).toEqual(expectedCells(deals))
  })
})
