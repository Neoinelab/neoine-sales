import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { gateway } from '../../gateway'
import { formatThousandWon } from '../../shared/model/money'
import type { ForecastSummary } from '../../shared/model/types'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { renderAt } from '../../test/mockApp'

/** P6 AC-11: 담당자 선택 시 같은 화면의 Deal 목록. 서버 한도(limit 200)와 요약 행 값 사용을 고정한다. */
const NOW = '2026-10-15T09:00:00+09:00'

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const SELECTED = `/forecast?year=2026&quarter=4&sel=${USER_ID.kim}`
/** 요약 응답 `columns`(서버가 Lost를 이미 뺀 열) 중 Lost가 아닌 key 전부, 알파벳순. 링크의 `forecast`와 목록 조회의 forecastKeys가 이 값이다. */
const NOT_LOST_KEYS = ['best', 'commit', 'most_likely', 'pipeline', 'won']

describe('담당자 Deal 목록 요청 한도 (P6 AC-11)', () => {
  it('asks for at most 200 deals so the server does not answer 422', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(SELECTED)

    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await waitFor(() => expect(list).toHaveBeenCalled())

    expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, quarters: [4], limit: 200 }))
    for (const [query] of list.mock.calls) expect(query.limit ?? 0).toBeLessThanOrEqual(200)
  })

  it('shows the owner deals without an error banner (the default gateway enforces the server limit)', async () => {
    await renderAt(SELECTED)

    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(0))
    expect(within(section).queryByRole('alert')).not.toBeInTheDocument()
  })

  it('sorts the deals by Expected Close ascending', async () => {
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(1))

    const all = (await gateway.deals.list({ ownerId: USER_ID.kim, year: 2026, limit: 200 })).items
    const expected = all
      .filter((d) => d.forecastKey !== 'lost') // Lost는 표에서 제외한다(R3 AC3-5)
      .sort((a, b) => a.revenueDate.localeCompare(b.revenueDate) || a.code.localeCompare(b.code))
      .map((d) => d.name)
    expect(within(section).getAllByRole('link').map((a) => a.textContent)).toEqual(expected)
  })

  it('passes the month of the summary to the owner deal list', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/forecast?year=2026&month=11&sel=${USER_ID.kim}`)

    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, month: 11 })))
    for (const [query] of list.mock.calls) expect(query.quarters).toBeUndefined()
  })
})

describe('200건 초과 안내 (P6 AC-11)', () => {
  /** 서버가 200건 한도로 답하면서 조건에 맞는 전체는 250건이라고 알려 주는 상황. */
  function fakeLongList(): void {
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => ({ ...(await original(query)), total: 250, limit: 200 }))
  }

  it('says how many of the total are shown', async () => {
    fakeLongList()
    await renderAt(`/forecast?year=2026&quarter=4&sel=${USER_ID.kim}`)

    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    expect(await within(section).findByText(/총 250건 중 200건/)).toBeVisible()
  })

  it('links to the Deals list with the same owner, period and vendor conditions plus the not-lost forecast set', async () => {
    fakeLongList()
    await renderAt(`/forecast?year=2026&quarter=4&vendor=7&sel=${USER_ID.kim}`)

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

  it('uses month instead of quarter in the link for a month period', async () => {
    fakeLongList()
    await renderAt(`/forecast?year=2026&month=11&sel=${USER_ID.kim}`)

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

  it('shows neither the notice nor the link when everything fits in one request', async () => {
    await renderAt(SELECTED)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(0))

    expect(within(section).queryByText(/건 중 200건/)).not.toBeInTheDocument()
    expect(within(section).queryByRole('link', { name: /Deals 목록에서 모두 보기/ })).not.toBeInTheDocument()
  })
})

describe('목록 위 Open 요약은 요약 표 행의 값이다 (P6 AC-11)', () => {
  /** 요약 행의 Open 값을 목록에서 계산할 수 없는 값으로 바꾼 서버 응답. */
  async function summaryWithDistinctOpen(): Promise<ForecastSummary> {
    const real = await gateway.forecast.summary({ year: 2026, quarter: 4 })
    return {
      ...real,
      rows: real.rows.map((row) => (row.ownerId === USER_ID.kim ? { ...row, total: { count: 77, amount: 7_777_000 } } : row)),
    }
  }

  it('shows the server row value instead of recomputing from the listed deals', async () => {
    const summary = await summaryWithDistinctOpen()
    vi.spyOn(gateway.forecast, 'summary').mockResolvedValue(summary)
    await renderAt(SELECTED)

    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(section).toHaveTextContent(`Open 77건 · 금액(단위:천원) ${formatThousandWon(7_777_000)}`))
  })

  it('does not list the Lost deals and says nothing about them any more', async () => {
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(0))
    expect(within(section).queryByRole('link', { name: '새론병원 SSO' })).not.toBeInTheDocument()
    expect(section).not.toHaveTextContent(/Lost \d+건/)
    expect(section).not.toHaveTextContent('합계에서 제외')
  })
})

describe('담당자 Deal 표는 Lost를 뺀다 (R3 AC3-5, Q2=B)', () => {
  const KIM_2026 = `/forecast?year=2026&sel=${USER_ID.kim}`

  function fakeTotal(total: number): void {
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => ({ ...(await original(query)), total, limit: 200 }))
  }

  it('asks the list with the not-lost forecast keys of the summary columns', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(KIM_2026)
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, forecastKeys: NOT_LOST_KEYS })))
    for (const [query] of list.mock.calls) expect(query.forecastKeys).not.toContain('lost')
  })

  it('uses the keys of the response columns, so an open code added by the admin is included', async () => {
    const real = await gateway.forecast.summary({ year: 2026 })
    vi.spyOn(gateway.forecast, 'summary').mockResolvedValue({
      ...real,
      columns: [...real.columns, { key: 'verbal', name: 'Verbal', outcome: 'open', order: 99 }],
    })
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(KIM_2026)
    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ forecastKeys: [...NOT_LOST_KEYS, 'verbal'].sort() })))
  })

  it.each([150, 200, 201, 250])('never mentions Lost deals whatever the total (%i)', async (total) => {
    fakeTotal(total)
    await renderAt(KIM_2026)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(within(section).getAllByRole('link').length).toBeGreaterThan(0))
    expect(section).not.toHaveTextContent(/Lost \d+건/)
    expect(section).not.toHaveTextContent('합계에서 제외')
  })

  it('counts the total without the Lost deals (the list asked for is the not-lost one)', async () => {
    const lostFree = (await gateway.deals.list({ ownerId: USER_ID.kim, year: 2026, forecastKeys: NOT_LOST_KEYS, limit: 200 })).total
    const withLost = (await gateway.deals.list({ ownerId: USER_ID.kim, year: 2026, limit: 200 })).total
    expect(withLost).toBeGreaterThan(lostFree)
    await renderAt(KIM_2026)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(within(section).getAllByRole('link')).toHaveLength(lostFree))
  })
})

describe('Deals 목록 링크 (R3 AC3-1~3)', () => {
  function fakeLongList(): void {
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => ({ ...(await original(query)), total: 250, limit: 200 }))
  }

  it('opens the Deals list with the Lost 제외 forecast filter and no Lost deal', async () => {
    fakeLongList()
    const { user, location } = await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await user.click(await within(section).findByRole('link', { name: /Deals 목록에서 모두 보기/ }))

    await waitFor(() => expect(location()).toMatch(/^\/deals\?/))
    const params = new URLSearchParams(location().split('?')[1])
    expect(params.get('forecast')).toBe(NOT_LOST_KEYS.join(','))
    expect(await screen.findByRole('button', { name: 'Forecast Lost 제외' })).toBeInTheDocument()
    expect(await screen.findByRole('row', { name: /ITDR/ })).toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /새론병원 SSO/ })).not.toBeInTheDocument()
  })

  it('draws no link when the summary has no not-lost column, and does not ask for an unfiltered list', async () => {
    const real = await gateway.forecast.summary({ year: 2026 })
    vi.spyOn(gateway.forecast, 'summary').mockResolvedValue({ ...real, columns: [] })
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)

    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    expect(await within(section).findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
    expect(within(section).queryByRole('link', { name: /Deals 목록에서 모두 보기/ })).not.toBeInTheDocument()
    expect(list).not.toHaveBeenCalled()
  })

  it('keeps the owner list hidden in snapshot mode (no link either)', async () => {
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}&snap=2026-09`)

    await screen.findByRole('heading', { name: 'Forecast' })

    expect(screen.queryByRole('region', { name: '선택한 담당자: 김영업' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /Deals 목록에서 모두 보기/ })).not.toBeInTheDocument()
  })
})
