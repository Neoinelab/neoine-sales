import { screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { resetMock } from '../../test/fake/default'
import { USER_ID } from '../../test/fake/seed/ids'
import { clickBar, clickEmptyArea, lastChart, renderedCharts } from '../../test/chartMock'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { seedVendorId } from '../../test/fixtures/vendors'
import { renderAt } from '../../test/mockApp'
import { canvases, mockSummary, NOW } from './testHelpers'

/**
 * Status 막대 차트(AC-13·16·21). react-chartjs-2는 setup.ts의 전역 mock(test/chartMock)이 바꿔 끼워 받은 data·options를 기록한다.
 * 막대 높이는 금액(원), 건수는 축 라벨 `이름 (N건)`에 둔다. 막대를 누르면 표의 행 링크와 같은 곳으로 이동한다.
 */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

const STATUS_LABELS = [
  '기회발굴 (14건)',
  '제품소개 (6건)',
  'POC준비 (4건)',
  'POC완료 (3건)',
  '기술평가 (2건)',
  '가격협상 (2건)',
  '계약완료 (2건)',
]
const AMOUNTS = [250_000_000, 110_000_000, 80_000_000, 70_000_000, 60_000_000, 60_000_000, 40_000_000]

async function openStatusTab(url = '/dashboard?year=2026') {
  mockSummary(dashboardSummaryFixture())
  const view = await renderAt(url)
  await screen.findByRole('table')
  return view
}

describe('차트 데이터', () => {
  it('has one bar per status in code order, labelled with the name and the count', async () => {
    await openStatusTab()

    expect(lastChart().data.labels).toEqual(STATUS_LABELS)
  })

  it('uses the amount (won) as the bar height in a single dataset', async () => {
    await openStatusTab()

    const { datasets } = lastChart().data
    expect(datasets).toHaveLength(1)
    expect(datasets[0]?.data).toEqual(AMOUNTS)
  })

  it('shows a status with no deals as a zero bar', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      statuses: { ...base.statuses, items: base.statuses.items.map((i) => (i.key === 'poc_completed' ? { ...i, count: 0, amount: 0 } : i)) },
    })
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    expect(lastChart().data.labels?.[3]).toBe('POC완료 (0건)')
    expect(lastChart().data.datasets[0]?.data[3]).toBe(0)
  })

  it('follows a renamed status code in the label', async () => {
    const base = dashboardSummaryFixture()
    mockSummary({
      ...base,
      statuses: { ...base.statuses, items: base.statuses.items.map((i) => (i.key === 'prospecting' ? { ...i, name: '발굴' } : i)) },
    })
    await renderAt('/dashboard?year=2026')
    await screen.findByRole('table')

    expect(lastChart().data.labels?.[0]).toBe('발굴 (14건)')
  })

  it('is not drawn on the Forecast tab', async () => {
    mockSummary(dashboardSummaryFixture())
    await renderAt('/dashboard?tab=forecast&year=2026')
    await screen.findByRole('table')

    expect(renderedCharts().every((chart) => chart.data.labels?.[0] !== STATUS_LABELS[0])).toBe(true)
  })
})

describe('막대 클릭은 Deal 목록으로 이동한다 (AC-16)', () => {
  it('opens the clicked status without Lost deals', async () => {
    const { location } = await openStatusTab()

    clickBar(lastChart(), { index: 2 })

    await waitFor(() => expect(location()).toBe('/deals?year=2026&status=poc_preparation&outcome=not_lost'))
  })

  it.each([
    [0, 'prospecting'],
    [3, 'poc_completed'],
    [6, 'contract_completed'],
  ])('opens the bar %i as status %s', async (index, key) => {
    const { location } = await openStatusTab()

    clickBar(lastChart(), { index })

    await waitFor(() => expect(location()).toBe(`/deals?year=2026&status=${key}&outcome=not_lost`))
  })

  it('carries the quarter, owner and vendor of the Dashboard', async () => {
    const vendor = seedVendorId('Okta')
    const { location } = await openStatusTab(`/dashboard?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}`)

    clickBar(lastChart(), { index: 3 })

    await waitFor(() => expect(location()).toBe(`/deals?year=2026&quarter=3&owner=${USER_ID.kim}&vendor=${vendor}&status=poc_completed&outcome=not_lost`))
  })

  it('does nothing when the click hits no bar', async () => {
    const { location } = await openStatusTab()

    clickEmptyArea(lastChart())

    expect(location()).toBe('/dashboard?year=2026')
  })

  it('goes to the same place as the link of that table row', async () => {
    const { location } = await openStatusTab()
    const href = within(screen.getByRole('row', { name: /POC완료/ })).getByRole('link').getAttribute('href')

    clickBar(lastChart(), { index: 3 })

    await waitFor(() => expect(location()).toBe(href))
  })

  it('shows a pointer cursor over a bar and not elsewhere', async () => {
    await openStatusTab()
    const { onHover } = lastChart().options
    const target = document.createElement('canvas')
    const event = { native: { target } } as never

    onHover?.(event, [{ index: 0, datasetIndex: 0 }] as never, {} as never)
    expect(target.style.cursor).toBe('pointer')
    onHover?.(event, [] as never, {} as never)
    expect(target.style.cursor).not.toBe('pointer')
  })
})

describe('접근성 (AC-21)', () => {
  it('gives the chart area an image role and a summary label', async () => {
    await openStatusTab()

    const charts = canvases()
    expect(charts).toHaveLength(1)
    expect(charts[0]).toHaveAccessibleName(/.+/)
  })

  it('has a table row link for every bar that works with the keyboard', async () => {
    const { user, location } = await openStatusTab()
    const rowLink = within(screen.getByRole('row', { name: /가격협상/ })).getByRole('link')

    rowLink.focus()
    expect(rowLink).toHaveFocus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(location()).toBe('/deals?year=2026&status=price_negotiation&outcome=not_lost'))
  })

  it('reaches every row link and the total link with Tab', async () => {
    const { user } = await openStatusTab()
    const table = screen.getByRole('table')
    const links = within(table).getAllByRole('link')
    expect(links).toHaveLength(8)

    links[0]?.focus()
    for (const next of links.slice(1)) {
      await user.tab()
      expect(next).toHaveFocus()
    }
  })
})
