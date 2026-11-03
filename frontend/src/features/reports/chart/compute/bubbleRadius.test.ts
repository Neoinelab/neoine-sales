import { describe, expect, it } from 'vitest'
import { bubbleRadius } from './bubbleRadius'

/**
 * `bubbleRadius(sizes)` (Excel 확장 AC7): 반지름 = 4 + 26 * sqrt(크기 / 최대 크기). 면적이 크기에 비례하고 최대는 30px.
 * 반환 `{ radii: (number | null)[], skipped }`: 입력과 같은 길이이고 0 이하·빈 값 자리는 null(그리지 않음)이다.
 */

describe('bubbleRadius', () => {
  it('gives the largest size a radius of 30px', () => {
    expect(bubbleRadius([10, 40, 20]).radii[1]).toBeCloseTo(30, 10)
  })

  it('makes the area proportional to the size: a quarter of the size is half the radius span', () => {
    const { radii } = bubbleRadius([100, 25])

    expect(radii[1]).toBeCloseTo(17, 10) // 4 + 26 * sqrt(0.25)
  })

  it('keeps the same length and marks sizes of zero or less and empty sizes as not drawn', () => {
    const { radii, skipped } = bubbleRadius([100, 0, null, -5, 25])

    expect(radii).toHaveLength(5)
    expect(radii[1]).toBeNull()
    expect(radii[2]).toBeNull()
    expect(radii[3]).toBeNull()
    expect(radii[4]).toBeCloseTo(17, 10)
    expect(skipped).toBe(3)
  })

  it('returns only nulls when there is nothing to draw', () => {
    expect(bubbleRadius([0, null])).toEqual({ radii: [null, null], skipped: 2 })
  })

  it('draws a single positive size at the largest radius', () => {
    expect(bubbleRadius([7]).radii[0]).toBeCloseTo(30, 10)
  })
})
