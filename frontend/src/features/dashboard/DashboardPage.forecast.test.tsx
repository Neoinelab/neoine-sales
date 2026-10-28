import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { formatThousandWon } from '../../shared/model/money'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { dashboardSummaryFixture, emptyDashboardSummary } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { mockSummary, NOT_LOST_PARAM, NOW, OPEN_PARAM } from './testHelpers'

/** Forecast 탭(슬라이드 9): Forecast 타일, 분기 표(고른 분기 행), Closing Attention 타일. AC-15·16·18. Selected Quarter는 2026-10-28에 폐지됐다. */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const won = (n: number) => formatThousandWon(n)
const hrefsOf = (row: HTMLElement) => within(row).getAllByRole('link').map((a) => a.getAttribute('href'))

async function openForecastTab(url = '/dashboard?tab=forecast&forecast.year=2026', summary = dashboardSummaryFixture()) {
  mockSummary(summary)
  const view = await renderAt(url)
  await screen.findByRole('table')
  return view
}

describe('Forecast 탭의 Forecast 타일', () => {
  it('shows the same tiles as the Status tab', async () => {
    await openForecastTab()
    const top = within(screen.getByRole('region', { name: 'Forecast 구분별 금액(단위:천원)' }))

    const tile = top.getByRole('link', { name: /Pipeline/ })

    expect(tile).toHaveTextContent('18건')
    expect(tile).toHaveTextContent(won(320_000_000))
    expect(top.getByRole('link', { name: /Open 합계/ })).toHaveTextContent('31건')
    expect(top.getByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026)')
    expect(screen.queryByRole('link', { name: /Lost/ })).not.toBeInTheDocument()
  })
})

describe('분기 표 (AC-15)', () => {
  it('has the four quarters as rows under the header', async () => {
    await openForecastTab()

    const rows = within(screen.getByRole('table')).getAllByRole('row')

    expect(rows).toHaveLength(5)
    ;['Q1', 'Q2', 'Q3', 'Q4'].forEach((quarter, i) => expect(rows[i + 1]).toHaveTextContent(quarter))
  })

  it('shows the amount of each forecast code, the open total and the total (open + won) of a quarter', async () => {
    await openForecastTab()

    const q1 = screen.getByRole('row', { name: /Q1/ })

    for (const amount of [40_000_000, 20_000_000, 10_000_000, 100_000_000, 110_000_000]) {
      expect(q1).toHaveTextContent(won(amount))
    }
    const q3 = screen.getByRole('row', { name: /Q3/ })
    for (const amount of [100_000_000, 50_000_000, 30_000_000, 20_000_000, 200_000_000, 230_000_000]) {
      expect(q3).toHaveTextContent(won(amount))
    }
  })

  it('shows the forecast columns without Lost in the header, in code order', async () => {
    await openForecastTab()

    const header = within(screen.getByRole('table')).getAllByRole('columnheader').map((h) => h.textContent ?? '')

    expect(header.join('|')).not.toContain('Lost')
    const positions = ['Pipeline', 'Best', 'Most Likely', 'Commit', 'Won'].map((name) => header.findIndex((text) => text.includes(name)))
    expect(positions.every((p) => p >= 0)).toBe(true)
    expect(positions).toEqual([...positions].sort((a, b) => a - b))
  })

  it('links the cells and the total of a quarter to its deals', async () => {
    await openForecastTab()

    const hrefs = hrefsOf(screen.getByRole('row', { name: /Q2/ }))

    expect(hrefs).toContain('/deals?year=2026&quarter=2&forecast=pipeline')
    expect(hrefs).toContain('/deals?year=2026&quarter=2&forecast=best')
    expect(hrefs).toContain(`/deals?year=2026&quarter=2&forecast=${OPEN_PARAM}`)
    expect(hrefs).toContain(`/deals?year=2026&quarter=2&forecast=${NOT_LOST_PARAM}`)
    expect(hrefs).not.toContain('/deals?year=2026&quarter=2')
  })

  it('carries only the owner and vendor into the quarter cell links, never the chosen quarters', async () => {
    const vendor = seedVendorId('Okta')
    await openForecastTab(`/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=3%2C4&forecast.owner=${USER_ID.kim}&forecast.vendor=${vendor}`)

    const hrefs = hrefsOf(screen.getByRole('row', { name: /Q4/ }))

    expect(hrefs).toContain(`/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=pipeline`)
    expect(hrefs).toContain(`/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=${OPEN_PARAM}`)
    expect(hrefs).toContain(`/deals?year=2026&quarter=4&owner=${USER_ID.kim}&vendor=${vendor}&forecast=${NOT_LOST_PARAM}`)
  })

  it('shows all four quarters when none or all four are chosen', async () => {
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026')
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(5)
  })

  it('shows all four quarters for all four chosen buttons (they stay pressed)', async () => {
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C2%2C3%2C4')

    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(5)
    for (const n of [1, 2, 3, 4]) expect(within(screen.getByRole('group', { name: 'Quarter' })).getByRole('button', { name: `Q${n}` })).toHaveAttribute('aria-pressed', 'true')
  })
})

describe('고른 분기만 보이는 Quarter Closing Forecast (AC-16·18, Selected Quarter 폐지)', () => {
  it('shows only the chosen quarter rows in ascending order', async () => {
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=3%2C1')

    const rows = within(screen.getByRole('table')).getAllByRole('row')

    expect(rows).toHaveLength(3)
    expect(rows[1]).toHaveTextContent('Q1')
    expect(rows[2]).toHaveTextContent('Q3')
    expect(screen.queryByRole('row', { name: /Q2/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('row', { name: /Q4/ })).not.toBeInTheDocument()
  })

  it('shows one row for one chosen quarter', async () => {
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=4')

    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(2)
    expect(screen.getByRole('row', { name: /Q4/ })).toBeVisible()
  })

  it('does not mark any row as current or selected', async () => {
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')

    const marked = within(screen.getByRole('table'))
      .getAllByRole('row')
      .filter((row) => row.hasAttribute('aria-current'))
    expect(marked).toHaveLength(0)
  })

  it('has no Selected Quarter section (no heading, no group, no text)', async () => {
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')

    expect(screen.queryByRole('group', { name: 'Selected Quarter' })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Selected Quarter/ })).not.toBeInTheDocument()
    expect(screen.queryByText(/Selected Quarter/)).not.toBeInTheDocument()
  })

  it('ignores the old sq key', async () => {
    const { user, location } = await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&sq=3')

    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(5)
    expect(screen.queryByText(/Selected Quarter/)).not.toBeInTheDocument()
    await user.click(within(screen.getByRole('group', { name: 'Quarter' })).getByRole('button', { name: 'Q2' }))
    await waitFor(() => expect(location()).toContain('forecast.quarter=2'))
    expect(location()).not.toContain('sq=')
  })

  it('shows the tiles exactly as the server answered for the chosen quarters', async () => {
    const base = dashboardSummaryFixture()
    const [q1, , q3] = base.quarters
    const sum = (pick: (q: NonNullable<typeof q1>) => { count: number; amount: number }) =>
      [q1, q3].reduce((t, q) => ({ count: t.count + pick(q as NonNullable<typeof q1>).count, amount: t.amount + pick(q as NonNullable<typeof q1>).amount }), { count: 0, amount: 0 })
    const pipeline = sum((q) => q.cells.pipeline ?? { count: 0, amount: 0 })
    const summary = dashboardSummaryFixture({
      period: { year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' },
      forecast: { ...base.forecast, cells: { ...base.forecast.cells, pipeline } },
    })
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3', summary)

    const top = within(screen.getByRole('region', { name: 'Forecast 구분별 금액(단위:천원)' }))

    expect(top.getByRole('link', { name: /Pipeline/ })).toHaveTextContent(`${pipeline.count}건`)
    expect(top.getByRole('link', { name: /Pipeline/ })).toHaveTextContent(won(pipeline.amount))
    expect(top.getByRole('link', { name: /Won/ })).toHaveTextContent('Won (2026 Q1, Q3)')
  })

  it('shows the empty message when the visible quarter rows have no deal (AC-18)', async () => {
    const empty = emptyDashboardSummary()
    const full = dashboardSummaryFixture()
    const summary = { ...empty, quarters: empty.quarters.map((q) => (q.quarter === 2 || q.quarter === 4 ? (full.quarters[q.quarter - 1] ?? q) : q)) }
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3', summary)

    expect(await screen.findByText('조건에 맞는 Deal이 없습니다.')).toBeVisible()
  })

  it('shows no empty message when a visible quarter row has deals', async () => {
    await openForecastTab('/dashboard?tab=forecast&forecast.year=2026&forecast.quarter=1%2C3')

    expect(screen.queryByText('조건에 맞는 Deal이 없습니다.')).not.toBeInTheDocument()
  })
})

describe('Closing Attention 타일 (AC-15)', () => {
  it('shows this month, this quarter and the stale tiles', async () => {
    await openForecastTab()

    expect(screen.getByRole('link', { name: /이번 달.*10월.*Expected Close\s*4/ })).toHaveAttribute('href', `/deals?year=2026&month=10&forecast=${OPEN_PARAM}`)
    expect(screen.getByRole('link', { name: /이번 분기.*Expected Close\s*7/ })).toHaveAttribute('href', `/deals?year=2026&quarter=4&forecast=${OPEN_PARAM}`)
    expect(screen.getByRole('link', { name: /14일 이상 미업데이트\D*5/ })).toHaveAttribute('href', '/deals?stale=1')
  })

  it('does not show the overdue tile (it belongs to the Status tab)', async () => {
    await openForecastTab()

    expect(screen.queryByRole('link', { name: /기한초과/ })).not.toBeInTheDocument()
  })

  it('applies only the owner and vendor and uses the server month', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, closingThisMonth: { year: 2027, month: 1, count: 2 } } })
    await renderAt(`/dashboard?tab=forecast&year=2026&quarter=2&owner=${USER_ID.kim}`)

    const tile = await screen.findByRole('link', { name: /이번 달.*1월/ })

    expect(tile).toHaveAttribute('href', `/deals?year=2027&month=1&owner=${USER_ID.kim}&forecast=${OPEN_PARAM}`)
  })

  it('shows the alert setting as the stale days', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({ ...base, attention: { ...base.attention, staleDays: 21, stale: 1 } })
    await renderAt('/dashboard?tab=forecast&year=2026')

    expect(await screen.findByRole('link', { name: /21일 이상 미업데이트\D*1/ })).toBeVisible()
  })
})
