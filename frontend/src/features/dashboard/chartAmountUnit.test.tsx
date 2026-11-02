import { screen } from '@testing-library/react'
import type { TooltipItem } from 'chart.js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { lastChart } from '../../test/chartMock'
import { resetMock } from '../../test/fake/default'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { renderAt } from '../../test/mockApp'
import { wonTick } from './chartSetup'
import { canvases, mockSummary, NOW } from './testHelpers'

/** Dashboard 막대 차트의 금액 단위(AC-6): 축 제목·툴팁은 원 콤마 숫자, 눈금만 억·만 단축, 접근성 이름은 (단위:원). */

beforeEach(() => resetMock({ now: NOW }))
afterEach(() => {
  vi.restoreAllMocks()
  resetMock({ now: null })
})

type Scale = { title?: { text?: string }; ticks?: { callback?: (v: number | string) => string } }
const scalesOf = () => lastChart().options.scales as { y?: Scale }
const tooltipLabel = (item: Partial<TooltipItem<'bar'>>): string => {
  const tooltip = lastChart().options.plugins?.tooltip
  const label = tooltip?.callbacks?.label as ((i: unknown) => string) | undefined
  if (!label) throw new Error('툴팁 label 콜백이 없습니다.')
  return label(item)
}

async function openTab(url: string) {
  mockSummary(dashboardSummaryFixture())
  await renderAt(url)
  await screen.findByRole('table')
}

describe('wonTick', () => {
  it.each([
    [1_870_000_000, '18.7억'],
    [50_000_000, '5,000만'],
    [9_000, '9,000'],
    [0, '0'],
  ])('shortens axis ticks to eok and man: %i', (value, shown) => {
    expect(wonTick(value)).toBe(shown)
  })

  it('accepts the string tick values Chart.js may pass', () => {
    expect(wonTick('100000000')).toBe('1억')
  })
})

describe('Status 막대 차트 단위', () => {
  it('titles the vertical axis in won and shortens its ticks', async () => {
    await openTab('/dashboard?year=2026')

    expect(scalesOf().y?.title?.text).toBe('금액(단위:원)')
    expect(scalesOf().y?.ticks?.callback?.(1_870_000_000)).toBe('18.7억')
    expect(scalesOf().y?.ticks?.callback?.(50_000_000)).toBe('5,000만')
  })

  it('shows the tooltip as won with commas and no shortening', async () => {
    await openTab('/dashboard?year=2026')

    expect(tooltipLabel({ parsed: { x: 0, y: 1_870_000_000 } })).toBe('금액(단위:원): 1,870,000,000')
  })

  it('names the chart with the won unit', async () => {
    await openTab('/dashboard?year=2026')

    expect(canvases()[0]).toHaveAccessibleName(/금액\(단위:원\)/)
    expect(canvases()[0]).not.toHaveAccessibleName(/천원/)
  })
})

describe('Quarter 누적 막대 차트 단위', () => {
  it('titles the vertical axis in won and shortens its ticks', async () => {
    await openTab('/dashboard?tab=forecast&forecast.year=2026')

    expect(scalesOf().y?.title?.text).toBe('금액(단위:원)')
    expect(scalesOf().y?.ticks?.callback?.(1_870_000_000)).toBe('18.7억')
  })

  it('shows the tooltip as the series name and won with commas', async () => {
    await openTab('/dashboard?tab=forecast&forecast.year=2026')

    expect(tooltipLabel({ dataset: { label: 'Commit' }, parsed: { x: 0, y: 1_870_000_000 } } as never)).toBe('Commit: 1,870,000,000')
  })

  it('names the chart with the won unit', async () => {
    await openTab('/dashboard?tab=forecast&forecast.year=2026')

    expect(canvases()[0]).toHaveAccessibleName(/금액\(단위:원\)/)
  })
})
