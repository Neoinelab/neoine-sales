import { NONE_LABEL, type Pivot } from '../pivot'

export interface TreemapRow {
  upper: string
  /** 계열이 없으면(상위 한 단계) 없다. */
  lower?: string
  value: number
}

interface TreemapTree<G> {
  tree: TreemapRow[]
  groups: G
  skipped: number
}

/**
 * 행 키는 플러그인 예약 이름(group, groupIndex, label, path, children, _idx, _leaf)과 겹치면 안 된다.
 * 계열이 없으면(`hasSeries` false) 값 열 머리글 이름의 자식 단계를 만들지 않고 상위 한 단계만 둔다.
 * 트리맵: 범주(상위) × 데이터셋(하위) 행렬 → 플러그인 `tree` 데이터. 0 이하·빈 칸은 넣지 않는다.
 * 같은 이름이 한 조각으로 합쳐지지 않게 앞 N자로 자르지 않은 전체 이름(`titles`)을 쓴다.
 */
export function treemapTree(grid: Pivot, hasSeries?: true): TreemapTree<['upper', 'lower']>
export function treemapTree(grid: Pivot, hasSeries: boolean): TreemapTree<['upper'] | ['upper', 'lower']>
export function treemapTree(grid: Pivot, hasSeries = true): TreemapTree<['upper'] | ['upper', 'lower']> {
  const tree: TreemapRow[] = []
  let skipped = 0
  // 빈 이름은 플러그인이 행을 버리므로 '(없음)'으로 바꾼다.
  const named = (title: string): string => (title === '' ? NONE_LABEL : title)
  for (const set of grid.sets) {
    grid.titles.forEach((group, i) => {
      const value = set.cells[i]?.value ?? null
      if (value === null || value <= 0) skipped += 1
      else tree.push(hasSeries ? { upper: named(group), lower: named(set.title), value } : { upper: named(group), value })
    })
  }
  return { tree, groups: hasSeries ? ['upper', 'lower'] : ['upper'], skipped }
}
