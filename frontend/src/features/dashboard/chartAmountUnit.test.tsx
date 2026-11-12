import { screen } from '@testing-library/react'
import type { TooltipItem } from 'chart.js'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { lastChart } from '../../test/chartMock'
import { resetMock } from '../../test/fake/default'
import { dashboardSummaryFixture } from '../../test/fixtures/dashboardSummary'
import { renderAt } from '../../test/mockApp'
import { wonTick } from './chartSetup'
import { canvases, mockSummary, NOW } from './testHelpers'

/** Dashboard 막대 차트의 금액 단위: 축 제목·툴팁은 원 콤마 숫자, 눈금만 억·만 단축, 접근성 이름은 (단위:원). */

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
  // 테스트 코드: DSH-043
  it.each([
    [1_870_000_000, '18.7억'],
    [50_000_000, '5,000만'],
    [9_000, '9,000'],
    [0, '0'],
  ])('축 눈금을 억·만으로 줄인다: %i', (value, shown) => {
    // when: 눈금 값을 줄여 쓴다
    const text = wonTick(value)

    // then: 억·만 단위 표기다
    expect(text).toBe(shown)
  })

  // 테스트 코드: DSH-043
  it('Chart.js가 넘길 수 있는 문자열 눈금 값도 받는다', () => {
    // when: 문자열 눈금 값을 줄여 쓴다
    const text = wonTick('100000000')

    // then: 1억이다
    expect(text).toBe('1억')
  })
})

describe('Status 막대 차트 단위', () => {
  // 테스트 코드: DSH-043
  it('세로축 제목은 원 단위이고 눈금은 줄여 쓴다', async () => {
    // when: Status 탭을 연다
    await openTab('/dashboard?year=2026')

    // then: 세로축 제목이 "금액(단위:원)"이고 눈금이 억·만으로 줄어든다
    expect(scalesOf().y?.title?.text).toBe('금액(단위:원)')
    expect(scalesOf().y?.ticks?.callback?.(1_870_000_000)).toBe('18.7억')
    expect(scalesOf().y?.ticks?.callback?.(50_000_000)).toBe('5,000만')
  })

  // 테스트 코드: DSH-043
  it('툴팁은 원 콤마 숫자이고 줄여 쓰지 않는다', async () => {
    // when: Status 탭을 연다
    await openTab('/dashboard?year=2026')

    // then: 툴팁이 "금액(단위:원): 1,870,000,000"이다
    expect(tooltipLabel({ parsed: { x: 0, y: 1_870_000_000 } })).toBe('금액(단위:원): 1,870,000,000')
  })

  // 테스트 코드: DSH-043
  it('차트 이름에 원 단위가 들어간다', async () => {
    // when: Status 탭을 연다
    await openTab('/dashboard?year=2026')

    // then: 접근성 이름에 (단위:원)이 있고 천원은 없다
    expect(canvases()[0]).toHaveAccessibleName(/금액\(단위:원\)/)
    expect(canvases()[0]).not.toHaveAccessibleName(/천원/)
  })
})

describe('Quarter 누적 막대 차트 단위', () => {
  // 테스트 코드: DSH-046
  it('세로축 제목은 원 단위이고 눈금은 줄여 쓴다', async () => {
    // when: Forecast 탭을 연다
    await openTab('/dashboard?tab=forecast&forecast.year=2026')

    // then: 세로축 제목과 눈금이 원 단위·단축 표기다
    expect(scalesOf().y?.title?.text).toBe('금액(단위:원)')
    expect(scalesOf().y?.ticks?.callback?.(1_870_000_000)).toBe('18.7억')
  })

  // 테스트 코드: DSH-046
  it('툴팁은 계열 이름과 원 콤마 숫자다', async () => {
    // when: Forecast 탭을 연다
    await openTab('/dashboard?tab=forecast&forecast.year=2026')

    // then: 툴팁이 "Commit: 1,870,000,000"이다
    expect(tooltipLabel({ dataset: { label: 'Commit' }, parsed: { x: 0, y: 1_870_000_000 } } as never)).toBe('Commit: 1,870,000,000')
  })

  // 테스트 코드: DSH-046
  it('차트 이름에 원 단위가 들어간다', async () => {
    // when: Forecast 탭을 연다
    await openTab('/dashboard?tab=forecast&forecast.year=2026')

    // then: 접근성 이름에 (단위:원)이 있다
    expect(canvases()[0]).toHaveAccessibleName(/금액\(단위:원\)/)
  })
})
