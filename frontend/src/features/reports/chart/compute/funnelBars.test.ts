import { describe, expect, it } from 'vitest'
import { funnelBars } from './funnelBars'

/**
 * `funnelBars(values)` (Excel 확장 AC13): 0 이하·빈 값을 빼고 결과 순서대로 가운데 정렬 막대 `[-v/2, v/2]`.
 * 반환 `{ bars: { index, value, range: [number, number] }[], skipped }`. `index`는 입력에서의 원래 위치다.
 */

describe('funnelBars', () => {
  it('centers each bar around zero', () => {
    const { bars } = funnelBars([100, 60, 20])

    expect(bars.map((b) => b.range)).toEqual([
      [-50, 50],
      [-30, 30],
      [-10, 10],
    ])
    expect(bars.map((b) => b.value)).toEqual([100, 60, 20])
  })

  it('keeps the input order (no sorting)', () => {
    const { bars } = funnelBars([20, 100])

    expect(bars.map((b) => b.value)).toEqual([20, 100])
  })

  it('leaves out values of zero or less and empty values, keeping the original index', () => {
    const { bars, skipped } = funnelBars([100, 0, null, -3, 40])

    expect(bars.map((b) => [b.index, b.value])).toEqual([
      [0, 100],
      [4, 40],
    ])
    expect(skipped).toBe(3)
  })

  it('returns nothing when no value is positive', () => {
    expect(funnelBars([0, null])).toEqual({ bars: [], skipped: 2 })
  })
})
