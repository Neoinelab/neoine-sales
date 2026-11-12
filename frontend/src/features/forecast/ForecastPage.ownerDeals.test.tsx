import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { formatWon } from '../../shared/model/money'
import type { ForecastSummary } from '../../shared/model/types'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { renderAt } from '../../test/mockApp'

/** 담당자 선택 시 같은 화면의 Deal 목록. 서버 한도(limit 200)와 요약 행 값 사용을 고정한다. */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const SELECTED = `/forecast?year=2026&quarter=4&sel=${USER_ID.kim}`
/** 요약 응답 `columns`(서버가 Lost를 이미 뺀 열) 중 Lost가 아닌 key 전부, 알파벳순. 링크의 `forecast`와 목록 조회의 forecastKeys가 이 값이다. */
const NOT_LOST_KEYS = ['best', 'commit', 'most_likely', 'pipeline', 'won']

describe('담당자 Deal 목록 요청 한도', () => {
  // 테스트 코드: FC-069
  it('담당자 Deal 목록은 서버 한도에 맞춰 최대 200건만 요청한다', async () => {
    // given: Deal 목록 조회 스파이
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 김영업이 선택된 2026 Q4 화면을 연다
    await renderAt(SELECTED)

    // then: 조회가 담당자·연도·Q4·limit 200으로 나가고 어떤 조회도 200을 넘지 않는다
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await waitFor(() => expect(list).toHaveBeenCalled())

    expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, quarters: [4], limit: 200 }))
    for (const [query] of list.mock.calls) expect(query.limit ?? 0).toBeLessThanOrEqual(200)
  })

  // 테스트 코드: FC-067
  it('기본 게이트웨이로도 오류 배너 없이 담당자 Deal을 보인다', async () => {
    // when: 김영업이 선택된 화면을 연다
    await renderAt(SELECTED)

    // then: Deal 링크가 있고 오류 배너는 없다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(0))
    expect(within(section).queryByRole('alert')).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-069
  it('담당자 Deal은 Expected Close 오름차순으로 나온다', async () => {
    // when: 김영업이 선택된 2026 화면을 연다
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    // then: 링크 순서가 Expected Close 오름차순(Lost 제외)이다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(1))

    const all = (await gateway.deals.list({ ownerId: USER_ID.kim, year: 2026, limit: 200 })).items
    const expected = all
      .filter((d) => d.forecastKey !== 'lost') // Lost는 표에서 제외한다
      .sort((a, b) => a.revenueDate.localeCompare(b.revenueDate) || a.code.localeCompare(b.code))
      .map((d) => d.name)
    expect(within(section).getAllByRole('link').map((a) => a.textContent)).toEqual(expected)
  })

  // 테스트 코드: FC-069
  it('월 기간이면 담당자 Deal 목록 조회에 월을 보낸다', async () => {
    // given: Deal 목록 조회 스파이
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 2026년 11월에 김영업이 선택된 화면을 연다
    await renderAt(`/forecast?year=2026&month=11&sel=${USER_ID.kim}`)

    // then: 조회에 월이 담기고 분기는 없다
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, month: 11 })))
    for (const [query] of list.mock.calls) expect(query.quarters).toBeUndefined()
  })
})

describe('200건 초과 안내', () => {
  /** 서버가 200건 한도로 답하면서 조건에 맞는 전체는 250건이라고 알려 주는 상황. */
  function fakeLongList(): void {
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => ({ ...(await original(query)), total: 250, limit: 200 }))
  }

  // 테스트 코드: FC-070
  it('전체 건수와 보이는 건수를 안내한다', async () => {
    // given: 한도 200건으로 답하며 전체는 250건이라고 알리는 서버
    fakeLongList()
    // when: 김영업이 선택된 화면을 연다
    await renderAt(`/forecast?year=2026&quarter=4&sel=${USER_ID.kim}`)

    // then: "총 250건 중 200건" 안내가 보인다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    expect(await within(section).findByText(/총 250건 중 200건/)).toBeVisible()
  })

  // 테스트 코드: FC-070
  it('같은 담당자·기간·Vendor 조건과 Lost 아닌 Forecast 묶음으로 Deals 목록 링크를 건다', async () => {
    // given: 전체가 250건인 서버
    fakeLongList()
    // when: Vendor가 걸린 2026 Q4 화면을 연다
    await renderAt(`/forecast?year=2026&quarter=4&vendor=7&sel=${USER_ID.kim}`)

    // then: 링크의 경로와 쿼리가 담당자·연도·분기·Vendor·Lost 아닌 forecast 묶음이다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    const link = await within(section).findByRole('link', { name: /Deals 목록에서 모두 보기/ })

    const url = new URL(link.getAttribute('href') ?? '', 'http://localhost')
    expect(url.pathname).toBe('/deals')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      owner: String(USER_ID.kim),
      year: '2026',
      quarter: '4',
      vendor: '7',
      forecast: NOT_LOST_KEYS.join(','),
    })
  })

  // 테스트 코드: FC-070
  it('월 기간이면 링크에 분기 대신 월을 쓴다', async () => {
    // given: 전체가 250건인 서버
    fakeLongList()
    // when: 2026년 11월 화면을 연다
    await renderAt(`/forecast?year=2026&month=11&sel=${USER_ID.kim}`)

    // then: 링크 쿼리에 month가 있고 quarter는 없다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    const link = await within(section).findByRole('link', { name: /Deals 목록에서 모두 보기/ })

    const url = new URL(link.getAttribute('href') ?? '', 'http://localhost')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      owner: String(USER_ID.kim),
      year: '2026',
      month: '11',
      forecast: NOT_LOST_KEYS.join(','),
    })
  })

  // 테스트 코드: FC-070
  it('한 번에 다 담기면 안내와 링크가 없다', async () => {
    // when: 200건 안에 들어오는 담당자 화면을 연다
    await renderAt(SELECTED)
    // then: Deal 링크는 있고 초과 안내와 모두 보기 링크는 없다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(0))

    expect(within(section).queryByText(/건 중 200건/)).not.toBeInTheDocument()
    expect(within(section).queryByRole('link', { name: /Deals 목록에서 모두 보기/ })).not.toBeInTheDocument()
  })
})

describe('목록 위 Open 요약은 요약 표 행의 값이다', () => {
  /** 요약 행의 Open 값을 목록에서 계산할 수 없는 값으로 바꾼 서버 응답. */
  async function summaryWithDistinctOpen(): Promise<ForecastSummary> {
    const real = await gateway.forecast.summary({ year: 2026, quarter: 4 })
    return {
      ...real,
      rows: real.rows.map((row) => (row.ownerId === USER_ID.kim ? { ...row, total: { count: 77, amount: 7_777_000 } } : row)),
    }
  }

  // 테스트 코드: FC-068
  it('목록 위 Open 요약은 목록에서 다시 계산하지 않고 요약 행의 값이다', async () => {
    // given: 김영업 행의 Total을 목록으로 계산할 수 없는 값으로 바꾼 요약 응답
    const summary = await summaryWithDistinctOpen()
    vi.spyOn(gateway.forecast, 'summary').mockResolvedValue(summary)
    // when: 김영업이 선택된 화면을 연다
    await renderAt(SELECTED)

    // then: 목록 위 Open 요약이 요약 행의 값이다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(section).toHaveTextContent(`Open 77건 · 금액(단위:원) ${formatWon(7_777_000)}`))
  })

  // 테스트 코드: FC-068
  it('Lost Deal을 나열하지 않고 Lost 안내도 없다', async () => {
    // when: 김영업이 선택된 2026 화면을 연다
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    // then: Lost Deal 링크와 Lost 안내 문구가 없다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(0))
    expect(within(section).queryByRole('link', { name: '새론병원 SSO' })).not.toBeInTheDocument()
    expect(section).not.toHaveTextContent(/Lost \d+건/)
    expect(section).not.toHaveTextContent('합계에서 제외')
  })
})

describe('담당자 Deal 표는 Lost를 뺀다', () => {
  const KIM_2026 = `/forecast?year=2026&sel=${USER_ID.kim}`

  function fakeTotal(total: number): void {
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => ({ ...(await original(query)), total, limit: 200 }))
  }

  // 테스트 코드: FC-069
  it('요약 열 중 Lost 아닌 key 전부로 목록을 요청한다', async () => {
    // given: Deal 목록 조회 스파이
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 김영업이 선택된 화면을 연다
    await renderAt(KIM_2026)
    // then: 조회의 forecastKeys가 Lost 아닌 key 전부이고 lost는 없다
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, forecastKeys: NOT_LOST_KEYS })))
    for (const [query] of list.mock.calls) expect(query.forecastKeys).not.toContain('lost')
  })

  // 테스트 코드: FC-069
  it('응답 열의 key를 쓰므로 admin이 추가한 Open 코드도 포함한다', async () => {
    // given: 추가 Open 코드 "verbal" 열이 있는 요약 응답
    const real = await gateway.forecast.summary({ year: 2026 })
    vi.spyOn(gateway.forecast, 'summary').mockResolvedValue({
      ...real,
      columns: [...real.columns, { key: 'verbal', name: 'Verbal', outcome: 'open', order: 99 }],
    })
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 김영업이 선택된 화면을 연다
    await renderAt(KIM_2026)
    // then: 조회의 forecastKeys에 verbal이 들어간다
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ forecastKeys: [...NOT_LOST_KEYS, 'verbal'].sort() })))
  })

  // 테스트 코드: FC-068
  it.each([150, 200, 201, 250])('전체 건수와 관계없이 Lost Deal을 언급하지 않는다 (%i)', async (total) => {
    // given: 전체 건수를 바꾼 서버
    fakeTotal(total)
    // when: 김영업이 선택된 화면을 연다
    await renderAt(KIM_2026)
    // then: Lost 안내 문구가 없다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(0))
    expect(section).not.toHaveTextContent(/Lost \d+건/)
    expect(section).not.toHaveTextContent('합계에서 제외')
  })

  // 테스트 코드: FC-069
  it('Lost를 뺀 목록이므로 그만큼의 링크가 나온다', async () => {
    // given: Lost 포함·제외 목록의 건수
    const lostFree = (await gateway.deals.list({ ownerId: USER_ID.kim, year: 2026, forecastKeys: NOT_LOST_KEYS, limit: 200 })).total
    const withLost = (await gateway.deals.list({ ownerId: USER_ID.kim, year: 2026, limit: 200 })).total
    expect(withLost).toBeGreaterThan(lostFree)
    // when: 김영업이 선택된 화면을 연다
    await renderAt(KIM_2026)
    // then: 링크 수가 Lost 제외 건수와 같다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(within(section).getAllByRole('link')).toHaveLength(lostFree))
  })
})

describe('Deals 목록 링크', () => {
  function fakeLongList(): void {
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => ({ ...(await original(query)), total: 250, limit: 200 }))
  }

  // 테스트 코드: FC-071
  it('모두 보기 링크로 연 Deals 목록에는 Lost Deal이 없다', async () => {
    // given: 전체가 250건이라 모두 보기 링크가 있는 화면
    fakeLongList()
    const { user, location } = await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    // when: "Deals 목록에서 모두 보기" 링크를 누른다
    await user.click(await within(section).findByRole('link', { name: /Deals 목록에서 모두 보기/ }))

    // then: Deals 목록이 열려 forecast 묶음이 URL에 있고 Lost 제외 배지가 보이며 Lost Deal 행이 없다
    await waitFor(() => expect(location()).toMatch(/^\/deals\?/))
    const params = new URLSearchParams(location().split('?')[1])
    expect(params.get('forecast')).toBe(NOT_LOST_KEYS.join(','))
    expect(await screen.findByRole('button', { name: 'Forecast Lost 제외' })).toBeInTheDocument()
    expect(await screen.findByRole('row', { name: /ITDR/ })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /새론병원 SSO/ })).not.toBeInTheDocument()
  })

  // 테스트 코드: FC-072
  it('Lost 아닌 열이 없으면 링크를 그리지 않고 필터 없는 목록도 요청하지 않는다', async () => {
    // given: 열이 없는 요약 응답과 Deal 목록 조회 스파이
    const real = await gateway.forecast.summary({ year: 2026 })
    vi.spyOn(gateway.forecast, 'summary').mockResolvedValue({ ...real, columns: [] })
    const list = vi.spyOn(gateway.deals, 'list')
    // when: 김영업이 선택된 화면을 연다
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)

    // then: 빈 문구만 보이고 링크가 없으며 목록 조회가 한 번도 없다
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    expect(await within(section).findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(within(section).queryByRole('link', { name: /Deals 목록에서 모두 보기/ })).not.toBeInTheDocument()
    expect(list).not.toHaveBeenCalled()
  })

  // 테스트 코드: FC-080
  it('스냅숏 모드에서는 담당자 목록과 모두 보기 링크가 없다', async () => {
    // when: 스냅숏을 고른 채 담당자가 선택된 URL로 화면을 연다
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}&snap=2026-09`)

    // then: 담당자 영역과 링크가 없다
    await screen.findByRole('heading', { name: 'Forecast' })

    expect(screen.queryByRole('region', { name: '선택한 담당자: 김영업' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Deals 목록에서 모두 보기/ })).not.toBeInTheDocument()
  })
})
