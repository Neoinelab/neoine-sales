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

describe('담당자 Deal 목록 요청 한도 (P6 AC-11)', () => {
  it('asks for at most 200 deals so the server does not answer 422', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(SELECTED)

    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    await waitFor(() => expect(list).toHaveBeenCalled())

    expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, quarter: 4, limit: 200 }))
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
    const expected = [...all].sort((a, b) => a.revenueDate.localeCompare(b.revenueDate) || a.code.localeCompare(b.code)).map((d) => d.name)
    expect(within(section).getAllByRole('link').map((a) => a.textContent)).toEqual(expected)
  })

  it('passes the month of the summary to the owner deal list', async () => {
    const list = vi.spyOn(gateway.deals, 'list')
    await renderAt(`/forecast?year=2026&month=11&sel=${USER_ID.kim}`)

    await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    await waitFor(() => expect(list).toHaveBeenCalledWith(expect.objectContaining({ ownerId: USER_ID.kim, year: 2026, month: 11 })))
    for (const [query] of list.mock.calls) expect(query.quarter).toBeUndefined()
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

  it('links to the Deals list with the same owner, period and vendor conditions', async () => {
    fakeLongList()
    await renderAt(`/forecast?year=2026&quarter=4&vendor=7&sel=${USER_ID.kim}`)

    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    const link = await within(section).findByRole('link', { name: /Deals 목록에서 모두 보기/ })

    const url = new URL(link.getAttribute('href') ?? '', 'http://localhost')
    expect(url.pathname).toBe('/deals')
    expect(Object.fromEntries(url.searchParams)).toEqual({ owner: String(USER_ID.kim), year: '2026', quarter: '4', vendor: '7' })
  })

  it('uses month instead of quarter in the link for a month period', async () => {
    fakeLongList()
    await renderAt(`/forecast?year=2026&month=11&sel=${USER_ID.kim}`)

    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })
    const link = await within(section).findByRole('link', { name: /Deals 목록에서 모두 보기/ })

    const url = new URL(link.getAttribute('href') ?? '', 'http://localhost')
    expect(Object.fromEntries(url.searchParams)).toEqual({ owner: String(USER_ID.kim), year: '2026', month: '11' })
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

  it('still mentions the excluded Lost deals', async () => {
    await renderAt(`/forecast?year=2026&sel=${USER_ID.kim}`)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    expect(await within(section).findByRole('link', { name: '새론병원 SSO' })).toBeVisible()
    expect(section).toHaveTextContent('Lost')
    expect(section).toHaveTextContent('합계에서 제외')
  })
})

describe('Lost 제외 문구는 목록이 전부일 때만 보인다 (R1 Minor 1)', () => {
  const KIM_2026 = `/forecast?year=2026&sel=${USER_ID.kim}`

  function fakeTotal(total: number): void {
    const original = gateway.deals.list.bind(gateway.deals)
    vi.spyOn(gateway.deals, 'list').mockImplementation(async (query) => ({ ...(await original(query)), total, limit: 200 }))
  }

  it.each([150, 200])('shows the Lost note when the total is %i (at most the limit)', async (total) => {
    fakeTotal(total)
    await renderAt(KIM_2026)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    expect(await within(section).findByRole('link', { name: '새론병원 SSO' })).toBeVisible()
    expect(section).toHaveTextContent(/Lost \d+건/)
  })

  it.each([201, 250])('hides the Lost note when the total is %i (the list is cut at the limit)', async (total) => {
    fakeTotal(total)
    await renderAt(KIM_2026)
    const section = await screen.findByRole('region', { name: '선택한 담당자: 김영업' })

    expect(await within(section).findByText(new RegExp(`총 ${total}건 중 200건`))).toBeVisible()
    expect(section).not.toHaveTextContent(/Lost \d+건/)
  })
})
