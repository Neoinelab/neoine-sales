import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { clickBar, clickEmptyArea, lastChart } from '../../test/chartMock'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { canvases, mockSummary, NOW } from './testHelpers'

/**
 * 분기별 Closing Forecast 누적 막대(AC-15·16·21). 데이터셋 하나가 Forecast 열 하나(Lost 없음)이고 x축은 Q1~Q4다.
 * 막대 조각을 누르면(분기 = index, Forecast = datasetIndex) 그 분기·Forecast의 Deal 목록으로 이동한다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

async function openForecastTab(url = '/dashboard?tab=forecast&year=2026', summary = dashboardSummaryFixture()) {
  mockSummary(summary)
  const view = await renderAt(url)
  await screen.findByRole('table')
  return view
}

describe('차트 데이터', () => {
  it('has Q1 to Q4 on the axis', async () => {
    await openForecastTab()

    expect(lastChart().data.labels).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })

  it('has one dataset per forecast column in code order, without Lost, named after the code', async () => {
    await openForecastTab()

    expect(lastChart().data.datasets.map((d) => d.label)).toEqual(['Pipeline', 'Best', 'Most Likely', 'Commit', 'Won'])
  })

  it('holds the amount (won) of each quarter in every dataset', async () => {
    await openForecastTab()

    const [pipeline, best, mostLikely, commit, closed] = lastChart().data.datasets.map((d) => d.data)

    expect(pipeline).toEqual([40_000_000, 60_000_000, 100_000_000, 120_000_000])
    expect(best).toEqual([20_000_000, 30_000_000, 50_000_000, 50_000_000])
    expect(mostLikely).toEqual([0, 30_000_000, 30_000_000, 30_000_000])
    expect(commit).toEqual([40_000_000, 0, 20_000_000, 10_000_000])
    expect(closed).toEqual([10_000_000, 0, 30_000_000, 0])
  })

  it('stacks the bars on both axes', async () => {
    await openForecastTab()

    const scales = lastChart().options.scales as { x?: { stacked?: boolean }; y?: { stacked?: boolean } }
    expect(scales.x?.stacked).toBe(true)
    expect(scales.y?.stacked).toBe(true)
  })

  it('gives every forecast column its own colour', async () => {
    await openForecastTab()

    const colours = lastChart().data.datasets.map((d) => String(d.backgroundColor))

    expect(new Set(colours).size).toBe(colours.length)
  })

  it('adds a dataset for a forecast code the admin added, in code order', async () => {
    const base = dashboardSummaryFixture()
    const verbal = { key: 'verbal', name: 'Verbal', outcome: 'open' as const, order: 35 }
    await openForecastTab('/dashboard?tab=forecast&year=2026', {
      ...base,
      forecast: { ...base.forecast, columns: [...base.forecast.columns.slice(0, 3), verbal, ...base.forecast.columns.slice(3)] },
      quarters: base.quarters.map((q) => ({ ...q, cells: { ...q.cells, verbal: { count: 1, amount: 7_000_000 } } })),
    })

    expect(lastChart().data.datasets.map((d) => d.label)).toEqual(['Pipeline', 'Best', 'Most Likely', 'Verbal', 'Commit', 'Won'])
    expect(lastChart().data.datasets[3]?.data).toEqual([7_000_000, 7_000_000, 7_000_000, 7_000_000])
  })

  it('keeps all four quarters when sq is chosen', async () => {
    await openForecastTab('/dashboard?tab=forecast&year=2026&sq=3')

    expect(lastChart().data.labels).toEqual(['Q1', 'Q2', 'Q3', 'Q4'])
  })
})

describe('조각 클릭은 Deal 목록으로 이동한다 (AC-16)', () => {
  it('opens the clicked quarter and forecast code', async () => {
    const { location } = await openForecastTab()

    clickBar(lastChart(), { index: 1, datasetIndex: 3 })

    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=2&forecast=commit'))
  })

  it.each([
    [0, 0, 1, 'pipeline'],
    [3, 4, 4, 'won'],
    [2, 2, 3, 'most_likely'],
  ])('opens index %i of dataset %i as Q%i %s', async (index, datasetIndex, quarter, key) => {
    const { location } = await openForecastTab()

    clickBar(lastChart(), { index, datasetIndex })

    await waitFor(() => expect(location()).toBe(`/deals?year=2026&quarter=${quarter}&forecast=${key}`))
  })

  it('maps the dataset to its code key even when a code was added in the middle', async () => {
    const base = dashboardSummaryFixture()
    const verbal = { key: 'verbal', name: 'Verbal', outcome: 'open' as const, order: 35 }
    const { location } = await openForecastTab('/dashboard?tab=forecast&year=2026', {
      ...base,
      forecast: { ...base.forecast, columns: [...base.forecast.columns.slice(0, 3), verbal, ...base.forecast.columns.slice(3)] },
      quarters: base.quarters.map((q) => ({ ...q, cells: { ...q.cells, verbal: { count: 1, amount: 7_000_000 } } })),
    })

    clickBar(lastChart(), { index: 0, datasetIndex: 3 })

    await waitFor(() => expect(location()).toBe('/deals?year=2026&quarter=1&forecast=verbal'))
  })

  it('ignores the chosen Quarter and keeps only the owner and vendor', async () => {
    const vendor = seedVendorId('Okta')
    const { location } = await openForecastTab(`/dashboard?tab=forecast&year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}`)

    clickBar(lastChart(), { index: 0, datasetIndex: 1 })

    await waitFor(() => expect(location()).toBe(`/deals?year=2026&quarter=1&owner=${USER_ID.kim}&vendor=${vendor}&forecast=best`))
  })

  it('does nothing when the click hits no bar', async () => {
    const { location } = await openForecastTab()

    clickEmptyArea(lastChart())

    expect(location()).toBe('/dashboard?tab=forecast&year=2026')
  })

  it('goes to the same place as the table cell link of that quarter and code', async () => {
    const { location } = await openForecastTab()
    const links = within(screen.getByRole('row', { name: /Q3/ })).getAllByRole('link').map((a) => a.getAttribute('href'))

    clickBar(lastChart(), { index: 2, datasetIndex: 1 })

    await waitFor(() => expect(links).toContain(location()))
  })
})

describe('접근성 (AC-21)', () => {
  it('gives the chart area an image role and a summary label', async () => {
    await openForecastTab()

    const charts = canvases()
    expect(charts).toHaveLength(1)
    expect(charts[0]).toHaveAccessibleName(/.+/)
  })

  it('has table links that work with the keyboard', async () => {
    const { user, location } = await openForecastTab()
    const link = within(screen.getByRole('row', { name: /Q2/ })).getAllByRole('link')[0]
    if (!link) throw new Error('Q2 행에 링크가 없습니다.')
    const href = link.getAttribute('href')

    link.focus()
    expect(link).toHaveFocus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(location()).toBe(href))
  })
})
