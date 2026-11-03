import { describe, expect, it } from 'vitest'
import type { Pivot } from '../pivot'
import { sunburstRings } from './sunburstRings'

/**
 * `sunburstRings(pivot)` (Excel 확장 AC9): 범주(상위) × 데이터셋(하위) 행렬 → 두 고리.
 * 반환 `{ inner: { label, value }[], outer: { parent, label, value }[], skipped }`.
 * 안쪽 = 상위 합계, 바깥 = (상위, 하위) 쌍을 상위 순서대로. 두 고리의 합이 같아야 바깥 조각이 상위 각도 안에 맞는다.
 * 0 이하·빈 값은 그리지 않고 개수를 센다.
 */

const cell = (value: number | null) => ({ raw: value, column: {} as never, value })
function grid(labels: string[], sets: { label: string; values: (number | null)[] }[]): Pivot {
  return {
    labels,
    titles: labels,
    sets: sets.map((s) => ({ label: s.label, title: s.label, cells: s.values.map(cell) })),
  }
}

const SAMPLE = grid(['A', 'B'], [
  { label: 'x', values: [3, 1] },
  { label: 'y', values: [2, null] },
])

describe('sunburstRings', () => {
  it('sums each parent for the inner ring', () => {
    expect(sunburstRings(SAMPLE).inner).toEqual([
      { label: 'A', value: 5 },
      { label: 'B', value: 1 },
    ])
  })

  it('lists the children grouped by parent in the parent order for the outer ring', () => {
    expect(sunburstRings(SAMPLE).outer).toEqual([
      { parent: 'A', label: 'x', value: 3 },
      { parent: 'A', label: 'y', value: 2 },
      { parent: 'B', label: 'x', value: 1 },
    ])
  })

  it('makes both rings add up to the same total', () => {
    const { inner, outer } = sunburstRings(SAMPLE)

    expect(outer.reduce((a, b) => a + b.value, 0)).toBe(inner.reduce((a, b) => a + b.value, 0))
  })

  it('leaves out values of zero or less and empty values and counts them', () => {
    const result = sunburstRings(grid(['A', 'B'], [{ label: 'x', values: [3, 0] }, { label: 'y', values: [-1, null] }]))

    expect(result.outer).toEqual([{ parent: 'A', label: 'x', value: 3 }])
    expect(result.skipped).toBe(3)
  })

  it('drops a parent whose children are all left out from the inner ring', () => {
    const result = sunburstRings(grid(['A', 'B'], [{ label: 'x', values: [3, 0] }]))

    expect(result.inner).toEqual([{ label: 'A', value: 3 }])
  })

  it('keeps a parent with a single child', () => {
    const result = sunburstRings(grid(['A'], [{ label: 'x', values: [4] }]))

    expect(result.outer).toEqual([{ parent: 'A', label: 'x', value: 4 }])
    expect(result.inner).toEqual([{ label: 'A', value: 4 }])
  })
})
