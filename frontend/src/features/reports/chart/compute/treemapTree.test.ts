import { describe, expect, it } from 'vitest'
import type { Pivot } from '../pivot'
import { treemapTree } from './treemapTree'

/**
 * `treemapTree(pivot)` (Excel 확장 AC9): 범주(상위) × 데이터셋(하위) 행렬 → 트리맵 플러그인의 `tree` 데이터.
 * 반환 `{ tree: 행[], groups: [상위 키, 하위 키], skipped }`(행 = 두 키와 `value`). 0 이하·빈 값 칸은 넣지 않는다.
 */

const cell = (value: number | null) => ({ raw: value, column: {} as never, value })
const grid = (labels: string[], sets: { label: string; values: (number | null)[] }[]): Pivot => ({
  labels,
  titles: labels,
  sets: sets.map((s) => ({ label: s.label, title: s.label, cells: s.values.map(cell) })),
})

/**
 * 리뷰 후속(Major 1): 플러그인(chartjs-chart-treemap 4.2.2)은 묶음 노드를 만들 때 `group`·`groupIndex`·`label`·`path`·`children`을
 * 덮어쓰고 입력 행에는 `_idx`를 붙인다(dist esm `group()`, 380~384행). 행 키가 이 이름과 겹치면 상위 이름이 사라진다.
 * 그래서 키 이름은 `groups`로 읽고(이름을 고정하지 않는다) 예약 이름과 겹치지 않는지만 고정한다.
 */
const PLUGIN_RESERVED = ['group', 'groupIndex', 'label', 'path', 'children', '_idx', '_leaf']

describe('treemapTree', () => {
  it('makes one row per (parent, child) cell keyed by the two group keys', () => {
    const result = treemapTree(grid(['A', 'B'], [{ label: 'x', values: [3, 1] }, { label: 'y', values: [2, 4] }]))
    const [parent, child] = result.groups

    expect(result.tree as unknown as Record<string, unknown>[]).toEqual([
      { [parent]: 'A', [child]: 'x', value: 3 },
      { [parent]: 'B', [child]: 'x', value: 1 },
      { [parent]: 'A', [child]: 'y', value: 2 },
      { [parent]: 'B', [child]: 'y', value: 4 },
    ])
  })

  it('uses two different group keys that do not collide with the plugin reserved properties', () => {
    const result = treemapTree(grid(['A'], [{ label: 'x', values: [3] }]))
    const keys = new Set([...result.groups, ...Object.keys(result.tree[0] ?? {})])

    expect(new Set(result.groups).size).toBe(2)
    expect(PLUGIN_RESERVED.filter((name) => keys.has(name))).toEqual([])
  })

  it('leaves out values of zero or less and empty values and counts them', () => {
    const result = treemapTree(grid(['A', 'B'], [{ label: 'x', values: [3, 0] }, { label: 'y', values: [null, -2] }]))
    const [parent, child] = result.groups

    expect(result.tree as unknown as Record<string, unknown>[]).toEqual([{ [parent]: 'A', [child]: 'x', value: 3 }])
    expect(result.skipped).toBe(3)
  })

  it('returns an empty tree when nothing is positive', () => {
    expect(treemapTree(grid(['A'], [{ label: 'x', values: [0] }]))).toMatchObject({ tree: [], skipped: 1 })
  })

  /**
   * 재리뷰 Minor: 플러그인(chartjs-chart-treemap 4.2.2)은 그룹 값 ''을 빈 값으로 봐(hasGroupValue) 그 행의 하위 사각형을 지운다.
   * 상위·하위 이름이 빈 문자열이어도 행이 사라지지 않도록 "(없음)"으로 바꿔 넣는다.
   */
  it('replaces an empty child name with the none label so the row is kept', () => {
    const result = treemapTree(grid(['A', 'B'], [{ label: '', values: [5, null] }, { label: 'y', values: [3, null] }, { label: 'x', values: [null, 4] }]))
    const [parent, child] = result.groups

    expect(result.tree as unknown as Record<string, unknown>[]).toEqual([
      { [parent]: 'A', [child]: '(없음)', value: 5 },
      { [parent]: 'A', [child]: 'y', value: 3 },
      { [parent]: 'B', [child]: 'x', value: 4 },
    ])
  })

  it('replaces an empty parent name with the none label so the row is kept', () => {
    const result = treemapTree(grid(['', 'B'], [{ label: 'x', values: [5, 4] }]))
    const [parent, child] = result.groups

    expect(result.tree as unknown as Record<string, unknown>[]).toEqual([
      { [parent]: '(없음)', [child]: 'x', value: 5 },
      { [parent]: 'B', [child]: 'x', value: 4 },
    ])
  })

  it('never leaves an empty string in any group key', () => {
    const result = treemapTree(grid(['', 'B'], [{ label: '', values: [1, 2] }]))
    const rows = result.tree as unknown as Record<string, unknown>[]

    expect(rows.flatMap((row) => result.groups.map((key) => row[key])).filter((v) => v === '')).toEqual([])
  })
})
