import { describe, expect, it } from 'vitest'
import type { Pivot } from '../pivot'
import { treemapTree } from './treemapTree'

/**
 * `treemapTree(pivot)` (명세 RC-R49): 범주(상위) × 데이터셋(하위) 행렬 → 트리맵 플러그인의 `tree` 데이터.
 * 반환 `{ tree: 행[], groups: [상위 키, 하위 키], skipped }`(행 = 두 키와 `value`). 0 이하·빈 값 칸은 넣지 않는다.
 */

const cell = (value: number | null) => ({ raw: value, column: {} as never, value })
const grid = (labels: string[], sets: { label: string; values: (number | null)[] }[]): Pivot => ({
  labels,
  titles: labels,
  sets: sets.map((s) => ({ label: s.label, title: s.label, cells: s.values.map(cell) })),
})

/**
 * 플러그인(chartjs-chart-treemap 4.2.2)은 묶음 노드를 만들 때 `group`·`groupIndex`·`label`·`path`·`children`을
 * 덮어쓰고 입력 행에는 `_idx`를 붙인다(dist esm `group()`, 380~384행). 행 키가 이 이름과 겹치면 상위 이름이 사라진다.
 * 그래서 키 이름은 `groups`로 읽고(이름을 고정하지 않는다) 예약 이름과 겹치지 않는지만 고정한다.
 */
const PLUGIN_RESERVED = ['group', 'groupIndex', 'label', 'path', 'children', '_idx', '_leaf']

describe('treemapTree: 트리맵 행 계산', () => {
  // 테스트 코드: RC-095
  it('(상위, 하위) 칸마다 행 하나이고 두 그룹 키로 값을 담는다', () => {
    // when: 상위 2 × 하위 2 행렬로 트리를 만든다
    const result = treemapTree(grid(['A', 'B'], [{ label: 'x', values: [3, 1] }, { label: 'y', values: [2, 4] }]))
    const [parent, child] = result.groups

    // then: 칸마다 상위·하위·값 행이 순서대로 있다
    expect(result.tree as unknown as Record<string, unknown>[]).toEqual([
      { [parent]: 'A', [child]: 'x', value: 3 },
      { [parent]: 'B', [child]: 'x', value: 1 },
      { [parent]: 'A', [child]: 'y', value: 2 },
      { [parent]: 'B', [child]: 'y', value: 4 },
    ])
  })

  // 테스트 코드: RC-095
  it('두 그룹 키는 서로 다르고 플러그인 예약 이름과 겹치지 않는다', () => {
    // when: 칸 하나의 행렬로 트리를 만든다
    const result = treemapTree(grid(['A'], [{ label: 'x', values: [3] }]))
    const keys = new Set([...result.groups, ...Object.keys(result.tree[0] ?? {})])

    // then: 그룹 키가 둘이고 예약 이름이 하나도 없다
    expect(new Set(result.groups).size).toBe(2)
    expect(PLUGIN_RESERVED.filter((name) => keys.has(name))).toEqual([])
  })

  // 테스트 코드: RC-095
  it('0 이하·빈 칸은 넣지 않고 개수를 센다', () => {
    // when: 0·음수·빈 칸이 섞인 행렬로 트리를 만든다
    const result = treemapTree(grid(['A', 'B'], [{ label: 'x', values: [3, 0] }, { label: 'y', values: [null, -2] }]))
    const [parent, child] = result.groups

    // then: 양수 칸 하나만 남고 뺀 개수는 3이다
    expect(result.tree as unknown as Record<string, unknown>[]).toEqual([{ [parent]: 'A', [child]: 'x', value: 3 }])
    expect(result.skipped).toBe(3)
  })

  // 테스트 코드: RC-095
  it('양수가 없으면 빈 트리다', () => {
    // when: 양수가 없는 행렬로 트리를 만든다
    const actual = treemapTree(grid(['A'], [{ label: 'x', values: [0] }]))

    // then: 트리가 비고 뺀 개수가 1이다
    expect(actual).toMatchObject({ tree: [], skipped: 1 })
  })

  /**
   * 플러그인(chartjs-chart-treemap 4.2.2)은 그룹 값 ''을 빈 값으로 봐(hasGroupValue) 그 행의 하위 사각형을 지운다.
   * 상위·하위 이름이 빈 문자열이어도 행이 사라지지 않도록 "(없음)"으로 바꿔 넣는다.
   */
  // 테스트 코드: RC-095
  it('빈 하위 이름은 (없음)으로 바꿔 행을 지키지 않고 남긴다', () => {
    // when: 하위 이름이 빈 행렬로 트리를 만든다
    const result = treemapTree(grid(['A', 'B'], [{ label: '', values: [5, null] }, { label: 'y', values: [3, null] }, { label: 'x', values: [null, 4] }]))
    const [parent, child] = result.groups

    // then: 빈 하위 이름이 (없음)으로 바뀌어 행이 남는다
    expect(result.tree as unknown as Record<string, unknown>[]).toEqual([
      { [parent]: 'A', [child]: '(없음)', value: 5 },
      { [parent]: 'A', [child]: 'y', value: 3 },
      { [parent]: 'B', [child]: 'x', value: 4 },
    ])
  })

  // 테스트 코드: RC-095
  it('빈 상위 이름은 (없음)으로 바꿔 행을 남긴다', () => {
    // when: 상위 이름이 빈 행렬로 트리를 만든다
    const result = treemapTree(grid(['', 'B'], [{ label: 'x', values: [5, 4] }]))
    const [parent, child] = result.groups

    // then: 빈 상위 이름이 (없음)으로 바뀌어 행이 남는다
    expect(result.tree as unknown as Record<string, unknown>[]).toEqual([
      { [parent]: '(없음)', [child]: 'x', value: 5 },
      { [parent]: 'B', [child]: 'x', value: 4 },
    ])
  })

  // 테스트 코드: RC-095
  it('어떤 그룹 키에도 빈 글자를 남기지 않는다', () => {
    // when: 상위·하위 이름이 모두 빈 행렬로 트리를 만든다
    const result = treemapTree(grid(['', 'B'], [{ label: '', values: [1, 2] }]))
    const rows = result.tree as unknown as Record<string, unknown>[]

    // then: 그룹 키 값에 빈 글자가 없다
    expect(rows.flatMap((row) => result.groups.map((key) => row[key])).filter((v) => v === '')).toEqual([])
  })
})
