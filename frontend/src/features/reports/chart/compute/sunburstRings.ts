import type { Pivot } from '../pivot'

export interface SunburstRings {
  /** 안쪽 고리: 상위 수준(범주) 합계. */
  inner: { label: string; value: number }[]
  /** 바깥 고리: (상위, 하위) 쌍을 상위 순서대로. 안쪽 조각 각도 안에 맞는다(두 고리의 합이 같다). */
  outer: { parent: string; label: string; value: number }[]
  /** 0 이하이거나 빈 칸이라 그리지 않은 수. */
  skipped: number
}

/** 선버스트: 범주(상위) × 데이터셋(하위) 행렬 → 겹친 두 고리. */
export function sunburstRings(grid: Pivot): SunburstRings {
  const inner: SunburstRings['inner'] = []
  const outer: SunburstRings['outer'] = []
  let skipped = 0
  grid.labels.forEach((parent, i) => {
    let sum = 0
    for (const set of grid.sets) {
      const value = set.cells[i]?.value ?? null
      if (value === null || value <= 0) {
        skipped += 1
        continue
      }
      sum += value
      outer.push({ parent, label: set.label, value })
    }
    if (sum > 0) inner.push({ label: parent, value: sum })
  })
  return { inner, outer, skipped }
}
