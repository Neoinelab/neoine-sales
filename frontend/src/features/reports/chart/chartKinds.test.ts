import { describe, expect, it } from 'vitest'
import { CHART_FAMILIES, CHART_KINDS, CHART_POINTS_MAX, CHART_VALUES_MAX, kindLabel, kindRule } from './chartKinds'

/**
 * 종류별 규칙표(Excel 확장 계획 "설계 2", 33종). backend `KIND_RULES`와 같은 표이며 서버가 정본이다(차이는 저장 때 422로 드러난다).
 * 열: [key, 화면 이름, 분류 key, 최대 그룹핑 수, 최소 그룹핑 수, 계열 가능, 값 최소, 값 최대, 행/열 전환, 축 범위, 보조 축, 0~100 축, 범주 사용, 옵션]
 * 옵션은 서버 `ChartOption` 값(`histogram`·`show_total`·`combo_series`)이다.
 */
type Row = readonly [string, string, string, number, number, boolean, number, number, boolean, boolean, boolean, boolean, boolean, readonly string[]]

const none: readonly string[] = []
const cartesian = (key: string, label: string, family: string, percent = false): Row => [key, label, family, 2, 1, true, 1, 10, true, true, false, percent, true, none]
const xy = (key: string, label: string): Row => [key, label, 'xy', 1, 1, false, 2, 10, false, true, false, false, true, none]
const radar = (key: string, label: string): Row => [key, label, 'radar', 2, 1, true, 1, 10, true, true, false, false, true, none]

const TABLE: readonly Row[] = [
  cartesian('bar', '묶은 세로 막대', 'column'),
  cartesian('stacked_bar', '누적 세로 막대', 'column'),
  cartesian('stacked_100_bar', '100% 누적 세로 막대', 'column', true),
  cartesian('horizontal_bar', '묶은 가로 막대', 'bar'),
  cartesian('stacked_horizontal_bar', '누적 가로 막대', 'bar'),
  cartesian('stacked_100_horizontal_bar', '100% 누적 가로 막대', 'bar', true),
  cartesian('line', '꺾은선', 'line'),
  cartesian('line_markers', '표식이 있는 꺾은선', 'line'),
  cartesian('stacked_line', '누적 꺾은선', 'line'),
  cartesian('stacked_line_markers', '표식이 있는 누적 꺾은선', 'line'),
  cartesian('stacked_100_line', '100% 누적 꺾은선', 'line', true),
  cartesian('stacked_100_line_markers', '표식이 있는 100% 누적 꺾은선', 'line', true),
  ['pie', '원형', 'pie', 1, 1, false, 1, 1, false, false, false, false, true, none],
  ['doughnut', '도넛형', 'pie', 1, 1, false, 1, 1, false, false, false, false, true, none],
  cartesian('area', '영역', 'area'),
  cartesian('stacked_area', '누적 영역', 'area'),
  cartesian('stacked_100_area', '100% 누적 영역', 'area', true),
  xy('scatter', '분산형(표식만)'),
  xy('scatter_smooth_markers', '곡선 및 표식이 있는 분산형'),
  xy('scatter_smooth', '곡선이 있는 분산형'),
  xy('scatter_line_markers', '직선 및 표식이 있는 분산형'),
  xy('scatter_line', '직선이 있는 분산형'),
  ['bubble', '거품형', 'xy', 1, 1, false, 3, 3, false, true, false, false, true, none],
  radar('radar', '방사형'),
  radar('radar_markers', '표식이 있는 방사형'),
  radar('radar_filled', '채워진 방사형'),
  ['treemap', '트리맵', 'treemap', 2, 1, true, 1, 1, false, false, false, false, true, none],
  ['sunburst', '선버스트', 'sunburst', 2, 1, true, 1, 1, false, false, false, false, true, none],
  ['histogram', '히스토그램', 'histogram', 2, 0, false, 1, 1, false, true, false, false, false, ['histogram']],
  ['pareto', '파레토', 'histogram', 1, 1, false, 1, 1, false, true, false, false, true, none],
  ['waterfall', '폭포', 'waterfall', 1, 1, false, 1, 1, false, true, false, false, true, ['show_total']],
  ['funnel', '깔때기', 'funnel', 1, 1, false, 1, 1, false, false, false, false, true, none],
  ['combo', '콤보', 'combo', 1, 1, false, 2, 10, false, true, true, false, true, ['combo_series']],
]

const FAMILIES = [
  ['column', '세로 막대형'],
  ['bar', '가로 막대형'],
  ['line', '꺾은선형'],
  ['pie', '원형'],
  ['area', '영역형'],
  ['xy', '분산형(X, Y) 또는 거품형'],
  ['radar', '방사형'],
  ['treemap', '트리맵'],
  ['sunburst', '선버스트'],
  ['histogram', '히스토그램'],
  ['waterfall', '폭포'],
  ['funnel', '깔때기'],
  ['combo', '콤보'],
] as const

describe('chart kind rules (Excel 확장 AC1, AC2)', () => {
  it('lists the 33 kinds', () => {
    expect(CHART_KINDS).toHaveLength(33)
    expect(new Set(CHART_KINDS.map((k) => k.key)).size).toBe(33)
    expect(CHART_KINDS.map((k) => k.key).sort()).toEqual(TABLE.map((row) => row[0]).sort())
  })

  it.each(TABLE.map((row): [string, Row] => [row[0], row]))(
    'defines %s with its label and rules',
    (_name, row) => {
      const [key, label, family, maxGroups, minGroups, allowsSeries, valuesMin, valuesMax, allowsSwap, allowsValueRange, allowsSecondary, percentAxis, usesCategory, options] = row
      const kind = CHART_KINDS.find((k) => k.key === key)

      expect(kind).toMatchObject({ key, label, family, maxGroups, minGroups, allowsSeries, valuesMin, valuesMax, allowsSwap, allowsValueRange, allowsSecondary, percentAxis, usesCategory })
      expect([...(kind?.options ?? [])].sort()).toEqual([...options].sort())
    },
  )

  it('has the 13 families in the order of the Excel dialog', () => {
    expect(CHART_FAMILIES.map((f) => [f.key, f.label])).toEqual(FAMILIES)
  })

  it('puts every kind in a known family', () => {
    const keys = new Set(CHART_FAMILIES.map((f) => f.key))

    expect(CHART_KINDS.every((k) => keys.has(k.family))).toBe(true)
  })

  it('counts the sub kinds of each family like the plan table', () => {
    const counts = Object.fromEntries(CHART_FAMILIES.map((f) => [f.key, CHART_KINDS.filter((k) => k.family === f.key).length]))

    expect(counts).toEqual({ column: 3, bar: 3, line: 6, pie: 2, area: 3, xy: 6, radar: 3, treemap: 1, sunburst: 1, histogram: 2, waterfall: 1, funnel: 1, combo: 1 })
  })

  it('looks a rule and a label up by kind', () => {
    expect(kindRule('stacked_100_horizontal_bar').percentAxis).toBe(true)
    expect(kindLabel('radar_filled')).toBe('채워진 방사형')
  })

  it('allows zero groups and no category only for the histogram', () => {
    expect(CHART_KINDS.filter((k) => k.minGroups === 0).map((k) => k.key)).toEqual(['histogram'])
    expect(CHART_KINDS.filter((k) => !k.usesCategory).map((k) => k.key)).toEqual(['histogram'])
  })

  it('limits values to ten (the number of series colors) and points to one thousand', () => {
    expect(CHART_VALUES_MAX).toBe(10)
    expect(CHART_POINTS_MAX).toBe(1000)
  })
})
