import { describe, expect, it } from 'vitest'
import { CHART_KINDS } from '../../../features/reports/chart/chartKinds'
import { toChartKind } from './reportChart'

/** 매퍼가 받아들이는 종류 집합은 규칙표 `CHART_KINDS`의 키 집합과 같다. */
/** 서버 `ChartKind`와 같은 33개 키(명시 목록). */
const EXPECTED_KEYS = ['bar', 'stacked_bar', 'stacked_100_bar', 'horizontal_bar', 'stacked_horizontal_bar', 'stacked_100_horizontal_bar', 'line', 'line_markers', 'stacked_line', 'stacked_line_markers', 'stacked_100_line', 'stacked_100_line_markers', 'pie', 'doughnut', 'area', 'stacked_area', 'stacked_100_area', 'scatter', 'scatter_smooth_markers', 'scatter_smooth', 'scatter_line_markers', 'scatter_line', 'bubble', 'radar', 'radar_markers', 'radar_filled', 'treemap', 'sunburst', 'histogram', 'pareto', 'waterfall', 'funnel', 'combo']

describe('toChartKind: 종류 키 변환', () => {
  // 테스트 코드: RC-079
  it.each(EXPECTED_KEYS)('규칙표의 종류 키는 모두 그대로 받아들인다 (%s)', (kind) => {
    // when: 종류 키를 화면 종류로 바꾼다
    const actual = toChartKind(kind)

    // then: 같은 키다
    expect(actual).toBe(kind)
  })

  // 테스트 코드: RC-079
  it('규칙표에 없는 종류는 거절한다', () => {
    // when·then: 모르는 종류를 바꾸면 오류가 난다
    expect(() => toChartKind('surface_3d')).toThrow()
  })

  // 테스트 코드: RC-079
  it('받아들이는 종류 집합은 서버의 33개와 규칙표 키 집합이 같다', () => {
    // when: 기대 목록과 규칙표 키를 비교한다
    const actual = [...CHART_KINDS.map((k) => k.key)].sort()
    // then: 33개로 같은 집합이다
    expect(EXPECTED_KEYS).toHaveLength(33)
    expect(actual).toEqual([...EXPECTED_KEYS].sort())
  })
})
