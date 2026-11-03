import { describe, expect, it } from 'vitest'
import { waterfallSteps } from './waterfallSteps'

/**
 * `waterfallSteps(values, showTotal)` (Excel 확장 AC12): 결과 행 순서대로 앞 누계에서 시작하는 뜬 막대.
 * 반환 `{ from, to, kind: 'increase' | 'decrease' | 'total' }[]`. 빈 값은 0, 0은 증가로 본다.
 */

describe('waterfallSteps', () => {
  it('starts every bar at the running total of the bars before it', () => {
    const steps = waterfallSteps([100, 50, 30], false)

    expect(steps.map((s) => [s.from, s.to])).toEqual([
      [0, 100],
      [100, 150],
      [150, 180],
    ])
  })

  it('marks the direction of each bar and moves the running total down for a decrease', () => {
    const steps = waterfallSteps([100, -40, 25], false)

    expect(steps.map((s) => [s.from, s.to, s.kind])).toEqual([
      [0, 100, 'increase'],
      [100, 60, 'decrease'],
      [60, 85, 'increase'],
    ])
  })

  it('treats an empty value as 0', () => {
    const steps = waterfallSteps([10, null, 5], false)

    expect(steps.map((s) => [s.from, s.to])).toEqual([
      [0, 10],
      [10, 10],
      [10, 15],
    ])
  })

  it('adds a total bar from 0 to the final running total when asked', () => {
    const steps = waterfallSteps([100, -40], true)

    expect(steps).toHaveLength(3)
    expect(steps.at(-1)).toEqual({ from: 0, to: 60, kind: 'total' })
  })

  it('adds no total bar by default', () => {
    expect(waterfallSteps([100, -40], false).some((s) => s.kind === 'total')).toBe(false)
  })

  it('returns only the total bar of 0 for no values when asked', () => {
    expect(waterfallSteps([], true)).toEqual([{ from: 0, to: 0, kind: 'total' }])
    expect(waterfallSteps([], false)).toEqual([])
  })
})
