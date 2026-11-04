import { describe, expect, it } from 'vitest'
import { CHART_KINDS } from '../../../features/reports/chart/chartKinds'
import { toChartKind } from './reportChart'

/** 리뷰 후속 AC8 보호: 매퍼가 받아들이는 종류 집합은 규칙표 `CHART_KINDS`의 키 집합과 같다. */
/** 서버 `ChartKind`와 같은 33개 키(명시 목록). */
const EXPECTED_KEYS = ['bar', 'stacked_bar', 'stacked_100_bar', 'horizontal_bar', 'stacked_horizontal_bar', 'stacked_100_horizontal_bar', 'line', 'line_markers', 'stacked_line', 'stacked_line_markers', 'stacked_100_line', 'stacked_100_line_markers', 'pie', 'doughnut', 'area', 'stacked_area', 'stacked_100_area', 'scatter', 'scatter_smooth_markers', 'scatter_smooth', 'scatter_line_markers', 'scatter_line', 'bubble', 'radar', 'radar_markers', 'radar_filled', 'treemap', 'sunburst', 'histogram', 'pareto', 'waterfall', 'funnel', 'combo']

describe('toChartKind', () => {
  it.each(EXPECTED_KEYS)('accepts the kind %s', (kind) => {
    expect(toChartKind(kind)).toBe(kind)
  })

  it('rejects a kind that is not in the rule table', () => {
    expect(() => toChartKind('surface_3d')).toThrow()
  })

  it('has the 33 kinds, the same set as the rule table', () => {
    expect(EXPECTED_KEYS).toHaveLength(33)
    expect([...CHART_KINDS.map((k) => k.key)].sort()).toEqual([...EXPECTED_KEYS].sort())
  })
})
