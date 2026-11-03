import type { ReportChartInput, ReportChartKind, ReportResult } from '../../../shared/model/reportTypes'
import type { FormatContext } from '../designer/format/formatCell'
import { buildCartesian, isCartesianKind } from './build/cartesian'
import { buildCombo } from './build/combo'
import { CHART_MISMATCH, problem, type BuildInput, type BuildOutcome } from './build/common'
import { buildFunnel } from './build/funnel'
import { buildTreemap } from './build/hierarchy'
import { buildRadar } from './build/radar'
import { buildPie, buildSunburst } from './build/round'
import { buildHistogram, buildPareto } from './build/statistics'
import { buildWaterfall } from './build/waterfall'
import { buildBubble, buildScatter } from './build/xy'
import { kindRule } from './chartKinds'
import { resolveColumns, resolveHistogram } from './pivot'

export { CHART_MISMATCH, CHART_TOO_MANY, type BuiltChart } from './build/common'

type Builder = (build: BuildInput) => BuildOutcome

/** 히스토그램을 뺀 종류별 빌더. 히스토그램은 범주가 없어 값 열만 따로 확인한다. */
const BUILDERS: Partial<Record<ReportChartKind, Builder>> = {
  pie: buildPie,
  doughnut: buildPie,
  scatter: buildScatter,
  scatter_smooth_markers: buildScatter,
  scatter_smooth: buildScatter,
  scatter_line_markers: buildScatter,
  scatter_line: buildScatter,
  bubble: buildBubble,
  radar: buildRadar,
  radar_markers: buildRadar,
  radar_filled: buildRadar,
  treemap: buildTreemap,
  sunburst: buildSunburst,
  pareto: buildPareto,
  waterfall: buildWaterfall,
  funnel: buildFunnel,
  combo: buildCombo,
}

/**
 * 차트 설정(컬럼은 결과 열 index) + 조회 결과 → Chart.js에 넘길 `type`·`data`·`options`와 안내(`notes`).
 * 설정이 결과와 맞지 않거나 점이 1,000개를 넘으면 `{ problem }`을 돌려준다(틀린 차트를 그리지 않는다).
 */
export function buildChart(input: ReportChartInput, result: ReportResult, fmt: FormatContext): BuildOutcome {
  if (input.kind === 'histogram') {
    const value = resolveHistogram(input, result)
    return value ? buildHistogram(input, result, value) : problem(CHART_MISMATCH)
  }
  const columns = resolveColumns(input, result)
  if (!columns) return problem(CHART_MISMATCH)
  const build: BuildInput = { input, result, columns, fmt, rule: kindRule(input.kind) }
  const builder = isCartesianKind(input.kind) ? buildCartesian : BUILDERS[input.kind]
  return builder ? builder(build) : problem(CHART_MISMATCH)
}
