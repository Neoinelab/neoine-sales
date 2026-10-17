import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { resetMock } from '../../test/fake/default'
import { ApiError } from '../../shared/api/problem'
import { formatKrwShort } from '../../shared/model/money'
import type { DealRow } from '../../shared/model/types'
import { renderAt } from '../../test/mockApp'

/** 시드 날짜가 기준일 상대값이라 기준일을 고정한다(2026-10-15). */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const COLUMNS = ['commit', 'most_likely', 'best', 'pipeline'] as const

function cellText(count: number, amount: number): string {
  return count === 0 ? '—' : `${count}건 · ${formatKrwShort(amount)}`
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

async function ledger(query: { year: number; quarter?: 1 | 2 | 3 | 4; vendor?: string; ownerId?: string }): Promise<DealRow[]> {
  const page = await gateway.deals.list({ ...query, limit: 1000 })
  return page.items
}

function sumOf(deals: DealRow[], pick: (d: DealRow) => boolean): { count: number; amount: number } {
  const hit = deals.filter(pick)
  return { count: hit.length, amount: hit.reduce((s, d) => s + d.revenueAmount, 0) }
}

const OPEN = new Set(['pipeline', 'best', 'most_likely', 'commit'])

function expectedCells(deals: DealRow[]): string[] {
  const cols = COLUMNS.map((k) => sumOf(deals, (d) => d.forecastKey === k))
  const total = sumOf(deals, (d) => OPEN.has(d.forecastKey))
  const won = sumOf(deals, (d) => d.forecastKey === 'won')
  return [...cols, total, won].map((s) => cellText(s.count, s.amount))
}

describe('Forecast 요약 표', () => {
  it('T-FC-04 열 순서(Commit, Most Likely, Best, Pipeline, Total(Open), Won)와 담당자·합계 행을 보여 준다', async () => {
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    const headers = screen.getAllByRole('columnheader').map((h) => h.textContent)
    expect(headers).toEqual(['담당자', 'Commit', 'Most Likely', 'Best', 'Pipeline', 'Total(Open)', 'Won'])
    expect(screen.getByRole('button', { name: '김영업' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '박영업' })).toBeInTheDocument()
  })

  it('T-FC-04 합계 행과 담당자 행의 모든 셀이 Deal 목록 원장 합과 같다(Lost 제외)', async () => {
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    const deals = await ledger({ year: 2026 })
    expect(readRow('합계')).toEqual(expectedCells(deals))
    for (const owner of ['김영업', '박영업', '이영업', '정영업']) {
      const mine = deals.filter((d) => d.owner.name === owner)
      expect(readRow(owner)).toEqual(expectedCells(mine))
    }
  })

  it('T-FC-03 Total은 Open(Commit+Most Likely+Best+Pipeline) 합이고 Won·Lost를 포함하지 않는다', async () => {
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    const deals = await ledger({ year: 2026 })
    const lost = deals.filter((d) => d.forecastKey === 'lost')
    const won = deals.filter((d) => d.forecastKey === 'won')
    expect(lost.length).toBeGreaterThan(0)
    expect(won.length).toBeGreaterThan(0)
    const cells = readRow('합계')
    const openSum = sumOf(deals, (d) => OPEN.has(d.forecastKey))
    expect(cells[4]).toBe(cellText(openSum.count, openSum.amount))
    expect(cells[5]).toBe(cellText(won.length, won.reduce((s, d) => s + d.revenueAmount, 0)))
    // Lost를 더했다면 건수가 달라진다.
    expect(openSum.count + won.length + lost.length).toBe(deals.length)
    expect(screen.queryByRole('columnheader', { name: 'Lost' })).not.toBeInTheDocument()
  })

  it('T-FC-01 Expected Close 기준 분기 분류: 12/31은 해당 연도 Q4, 1/1은 다음 해 Q1', async () => {
    const { client, user } = await renderAt('/forecast?year=2026&quarter=4', { role: 'admin' })
    await screen.findByRole('rowheader', { name: '합계' })
    const find = async (keyword: string): Promise<DealRow> => {
      const hit = (await gateway.deals.list({ keyword })).items[0]
      if (!hit) throw new Error(`시드 Deal을 찾지 못했습니다: ${keyword}`)
      return hit
    }
    const dec = await find('누리통신 NGFW') // 이영업 Pipeline 650M
    const jan = await find('푸른물류 SSO') // 이영업 Pipeline 180M
    await gateway.deals.update(dec.code, { revenueDate: '2026-12-31' })
    await gateway.deals.update(jan.code, { revenueDate: '2027-01-01' })
    await client.invalidateQueries()

    await waitFor(() => expect(readRow('이영업')[3]).toBe(cellText(1, dec.revenueAmount)))
    expect(readRow('이영업')[3]).toBe('1건 · 650M')

    await user.selectOptions(screen.getByLabelText('연도'), '2027')
    await user.selectOptions(screen.getByLabelText('Quarter'), '1')
    await waitFor(() => expect(readRow('이영업')[3]).toBe('1건 · 180M'))
  })

  it('필터(연도·Quarter·Vendor)를 적용해도 합계가 원장 합과 같다', async () => {
    await renderAt('/forecast?year=2026&quarter=4&vendor=Silverfort')
    await screen.findByRole('rowheader', { name: '합계' })
    const deals = await ledger({ year: 2026, quarter: 4, vendor: 'Silverfort' })
    expect(deals.length).toBeGreaterThan(0)
    expect(readRow('합계')).toEqual(expectedCells(deals))
  })

  it('선택한 Quarter 요약 카드에 Open 건수·금액과 Won(별도)을 보여 준다', async () => {
    await renderAt('/forecast?year=2026&quarter=4')
    await screen.findByRole('rowheader', { name: '합계' })
    const deals = await ledger({ year: 2026, quarter: 4 })
    const open = sumOf(deals, (d) => OPEN.has(d.forecastKey))
    const won = sumOf(deals, (d) => d.forecastKey === 'won')
    const card = screen.getByRole('region', { name: '2026 Q4 요약' })
    expect(within(card).getByText(/Open 합계/)).toBeInTheDocument()
    expect(card).toHaveTextContent(`${open.count}건`)
    expect(card).toHaveTextContent(formatKrwShort(open.amount))
    expect(within(card).getByText(/Won/)).toBeInTheDocument()
    expect(card).toHaveTextContent(`${won.count}건`)
    expect(card).toHaveTextContent(formatKrwShort(won.amount))
  })

  it('퇴사 담당자도 행에 "(퇴사)"로 나온다', async () => {
    await renderAt('/forecast?year=2027&quarter=1')
    expect(await screen.findByRole('button', { name: '강퇴사(퇴사)' })).toBeInTheDocument()
  })
})

describe('담당자 선택: 같은 화면 아래 Deal 목록', () => {
  it('T-FC-05 담당자를 누르면 같은 화면 아래에 그 담당자의 Deal 목록과 Deal 상세 링크가 나온다', async () => {
    const { user, location } = await renderAt('/forecast?year=2026')
    const button = await screen.findByRole('button', { name: '김영업' })
    expect(button).toHaveAttribute('aria-pressed', 'false')
    expect(screen.queryByRole('region', { name: /선택한 담당자/ })).not.toBeInTheDocument()

    await user.click(button)

    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    expect(screen.getByRole('button', { name: '김영업' })).toHaveAttribute('aria-pressed', 'true')
    expect(location()).toContain('sel=u-kim')
    // 요약 표가 그대로 남아 있다(별도 화면 이동 없음).
    expect(location()).toContain('/forecast')
    expect(screen.getByRole('rowheader', { name: '합계' })).toBeInTheDocument()

    const heads = within(section)
      .getAllByRole('columnheader')
      .map((h) => h.textContent)
    expect(heads).toEqual(['Deal', 'Status', 'Forecast', '금액', 'Expected Close', 'Next Action'])

    const deals = (await ledger({ year: 2026, ownerId: 'u-kim' })).filter((d) => d.forecastKey !== 'lost')
    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThanOrEqual(deals.length))
    const first = deals.find((d) => d.name === '한빛은행 ITDR 도입')
    expect(first).toBeDefined()
    expect(within(section).getByRole('link', { name: '한빛은행 ITDR 도입' })).toHaveAttribute('href', `/deals/${first?.code}`)
    expect(within(section).queryByRole('link', { name: '박영업' })).not.toBeInTheDocument()
  })

  it('T-FC-04 선택한 담당자의 목록 합계(Lost 제외)가 요약 표의 그 담당자 행과 같다', async () => {
    const { user } = await renderAt('/forecast?year=2026')
    await user.click(await screen.findByRole('button', { name: '김영업' }))
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    const all = await ledger({ year: 2026, ownerId: 'u-kim' })
    const deals = all.filter((d) => d.forecastKey !== 'lost')
    await waitFor(() => expect(within(section).getAllByRole('link')).toHaveLength(all.length))
    const open = sumOf(deals, (d) => OPEN.has(d.forecastKey))
    expect(readRow('김영업')[4]).toBe(cellText(open.count, open.amount))
    expect(section).toHaveTextContent(`Open ${open.count}건`)
    expect(section).toHaveTextContent(formatKrwShort(open.amount))
  })

  it('Lost Deal은 목록에 보이지만 합계에서는 제외된다는 안내가 있다', async () => {
    await renderAt('/forecast?year=2026&sel=u-kim')
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    expect(await within(section).findByRole('link', { name: '새론병원 SSO' })).toBeInTheDocument()
    expect(section).toHaveTextContent('Lost')
    expect(section).toHaveTextContent('합계에서 제외')
  })

  it('선택 해제 버튼으로 목록을 닫고 URL에서 선택이 사라진다', async () => {
    const { user, location } = await renderAt('/forecast?year=2026&sel=u-kim')
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await user.click(screen.getByRole('button', { name: '선택 해제' }))
    expect(screen.queryByRole('region', { name: /선택한 담당자/ })).not.toBeInTheDocument()
    expect(location()).not.toContain('sel=')
  })

  it('같은 담당자 버튼을 다시 누르면 선택이 해제된다', async () => {
    const { user } = await renderAt('/forecast?year=2026&sel=u-kim')
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await user.click(screen.getByRole('button', { name: '김영업' }))
    expect(screen.queryByRole('region', { name: /선택한 담당자/ })).not.toBeInTheDocument()
  })

  it('"담당자 상세" 메뉴/링크는 없다', async () => {
    await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    expect(screen.queryByRole('link', { name: /담당자 상세/ })).not.toBeInTheDocument()
  })
})

describe('필터와 URL 유지', () => {
  it('T-FC-06 URL의 연도·Quarter·담당자·Vendor가 필터 컨트롤에 반영된다', async () => {
    await renderAt('/forecast?year=2026&quarter=4&owner=u-kim&vendor=Silverfort')
    await screen.findByRole('rowheader', { name: '합계' })
    expect(screen.getByLabelText('연도')).toHaveValue('2026')
    expect(screen.getByLabelText('Quarter')).toHaveValue('4')
    expect(screen.getByLabelText('담당자')).toHaveValue('u-kim')
    await waitFor(() => expect(screen.getByLabelText('Vendor')).toHaveValue('Silverfort'))
    // 담당자 필터가 걸리면 다른 담당자 행은 없다.
    expect(screen.queryByRole('button', { name: '박영업' })).not.toBeInTheDocument()
  })

  it('T-FC-06 필터를 바꾸면 URL 쿼리에 남고 새로 고침 없이 표가 바뀐다', async () => {
    const { user, location } = await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    const before = readRow('합계')

    await user.selectOptions(screen.getByLabelText('Quarter'), '4')
    expect(location()).toContain('quarter=4')
    await waitFor(() => expect(readRow('합계')).not.toEqual(before))

    await user.selectOptions(await screen.findByLabelText('Vendor'), 'Silverfort')
    expect(location()).toContain('vendor=Silverfort')

    await user.selectOptions(screen.getByLabelText('담당자'), 'u-kim')
    expect(location()).toContain('owner=u-kim')

    await user.selectOptions(screen.getByLabelText('Quarter'), '')
    expect(location()).not.toContain('quarter=')
  })

  it('연도를 바꾸면 URL의 year가 바뀐다', async () => {
    const { user, location } = await renderAt('/forecast?year=2026')
    await screen.findByRole('rowheader', { name: '합계' })
    await user.selectOptions(screen.getByLabelText('연도'), '2027')
    expect(location()).toContain('year=2027')
    await screen.findByRole('region', { name: /2027 .*요약/ })
  })

  it('year가 없으면 올해로 열린다', async () => {
    await renderAt('/forecast')
    await screen.findByLabelText('연도')
    expect(screen.getByLabelText('연도')).toHaveValue(String(new Date().getFullYear()))
  })
})

describe('상태와 접근 권한', () => {
  it('조건에 맞는 Deal이 없으면 빈 상태 문구를 보여 준다', async () => {
    await renderAt('/forecast?year=2020')
    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('rowheader', { name: '합계' })).not.toBeInTheDocument()
  })

  it('불러오는 동안 로딩 문구가 나온다', async () => {
    vi.spyOn(gateway.forecast, 'summary').mockReturnValue(new Promise(() => undefined))
    await renderAt('/forecast?year=2026')
    await waitFor(() => {
      const statuses = screen.getAllByRole('status')
      expect(statuses.some((s) => s.textContent?.includes('불러오는 중'))).toBe(true)
    })
    expect(screen.queryByRole('rowheader', { name: '합계' })).not.toBeInTheDocument()
  })

  it('요약 조회가 실패하면 오류를 role=alert로 보여 준다', async () => {
    vi.spyOn(gateway.forecast, 'summary').mockRejectedValue(
      new ApiError(500, { type: 'about:blank', title: '서버 오류', status: 500, detail: '요약을 불러오지 못했습니다.' }),
    )
    await renderAt('/forecast?year=2026')
    expect(await screen.findByRole('alert')).toHaveTextContent('요약을 불러오지 못했습니다.')
  })

  it.each(['admin', 'sales', 'user'] as const)('%s 역할도 조회할 수 있고 쓰기 동작은 없다', async (role) => {
    await renderAt('/forecast?year=2026', { role })
    expect(await screen.findByRole('rowheader', { name: '합계' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Forecast' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /등록|수정|삭제|저장/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /등록/ })).not.toBeInTheDocument()
  })

  it('요약 표는 가로 스크롤 영역 안에 있고 접근 가능한 이름을 가진다', async () => {
    await renderAt('/forecast?year=2026')
    const table = await screen.findByRole('table', { name: /담당자별 Forecast/ })
    expect(table.closest('.fc-scroll')).not.toBeNull()
  })
})
