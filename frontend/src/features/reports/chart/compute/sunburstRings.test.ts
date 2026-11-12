import { describe, expect, it } from 'vitest'
import type { Pivot } from '../pivot'
import { sunburstRings } from './sunburstRings'

/**
 * `sunburstRings(pivot)` (명세 RC-R50): 범주(상위) × 데이터셋(하위) 행렬 → 두 고리.
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

describe('sunburstRings: 선버스트 고리 계산', () => {
  // 테스트 코드: RC-096
  it('안쪽 고리는 상위별 합계다', () => {
    // when: 행렬로 선버스트 고리를 구한다
    const actual = sunburstRings(SAMPLE).inner

    // then: 안쪽 고리가 A 5, B 1이다
    expect(actual).toEqual([
      { label: 'A', value: 5 },
      { label: 'B', value: 1 },
    ])
  })

  // 테스트 코드: RC-096
  it('바깥 고리는 상위 순서대로 하위를 묶어 나열한다', () => {
    // when: 행렬로 선버스트 고리를 구한다
    const actual = sunburstRings(SAMPLE).outer

    // then: 바깥 고리가 A-x, A-y, B-x 순서다
    expect(actual).toEqual([
      { parent: 'A', label: 'x', value: 3 },
      { parent: 'A', label: 'y', value: 2 },
      { parent: 'B', label: 'x', value: 1 },
    ])
  })

  // 테스트 코드: RC-097
  it('두 고리의 합계가 같다', () => {
    // when: 행렬로 선버스트 고리를 구한다
    const { inner, outer } = sunburstRings(SAMPLE)

    // then: 바깥 고리의 합이 안쪽 고리의 합과 같다
    expect(outer.reduce((a, b) => a + b.value, 0)).toBe(inner.reduce((a, b) => a + b.value, 0))
  })

  // 테스트 코드: RC-097
  it('0 이하·빈 값은 그리지 않고 개수를 센다', () => {
    // when: 0·음수·빈 칸이 섞인 행렬로 고리를 구한다
    const result = sunburstRings(grid(['A', 'B'], [{ label: 'x', values: [3, 0] }, { label: 'y', values: [-1, null] }]))

    // then: 양수 칸만 바깥에 남고 뺀 개수는 3이다
    expect(result.outer).toEqual([{ parent: 'A', label: 'x', value: 3 }])
    expect(result.skipped).toBe(3)
  })

  // 테스트 코드: RC-097
  it('하위가 모두 빠진 상위는 안쪽 고리에서도 뺀다', () => {
    // when: B의 하위가 모두 0인 행렬로 고리를 구한다
    const result = sunburstRings(grid(['A', 'B'], [{ label: 'x', values: [3, 0] }]))

    // then: 안쪽 고리에 A만 남는다
    expect(result.inner).toEqual([{ label: 'A', value: 3 }])
  })

  // 테스트 코드: RC-096
  it('하위가 하나인 상위는 그대로 둔다', () => {
    // when: 상위 하나에 하위 하나인 행렬로 고리를 구한다
    const result = sunburstRings(grid(['A'], [{ label: 'x', values: [4] }]))

    // then: 바깥·안쪽 고리에 각각 하나씩 있다
    expect(result.outer).toEqual([{ parent: 'A', label: 'x', value: 4 }])
    expect(result.inner).toEqual([{ label: 'A', value: 4 }])
  })
})
