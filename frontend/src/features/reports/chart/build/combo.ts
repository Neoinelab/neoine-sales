import type { ChartOptions } from 'chart.js'
import type { ReportChartInput, ReportComboSeries, ReportComboSeriesType } from '../../../../shared/model/reportTypes'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { pivot } from '../pivot'
import { axis, baseOptions, chartData, color, describe, gridCallbacks, NEAR_POINT, pluginsOf, rangeOf, secondaryAxis, tooMany, withAlpha, type BuildInput, type BuildOutcome, type Datasets } from './common'

export interface ComboPreset {
  key: 'column_line' | 'column_line_secondary' | 'area_column'
  label: string
  /** 값 열 수만큼의 계열 설정. */
  apply: (count: number) => ReportComboSeries[]
}

const series = (type: ReportComboSeriesType, secondary = false): ReportComboSeries => ({ type, secondary })

/** 콤보 프리셋(화면 바로가기일 뿐 저장하지 않는다). 사용자 지정 조합은 프리셋이 아니라 '현재 값 유지'다. */
export const COMBO_PRESETS: readonly ComboPreset[] = [
  { key: 'column_line', label: '묶은 세로 막대 - 꺾은선', apply: (count) => Array.from({ length: count }, (_, i) => series(i === 0 ? 'column' : 'line')) },
  {
    key: 'column_line_secondary',
    label: '묶은 세로 막대 - 보조 축의 꺾은선',
    apply: (count) => Array.from({ length: count }, (_, i) => (i === 0 ? series('column') : series('line', true))),
  },
  { key: 'area_column', label: '누적 영역 - 묶은 세로 막대', apply: (count) => Array.from({ length: count }, (_, i) => series(i === count - 1 ? 'column' : 'stacked_area')) },
]

const same = (a: readonly ReportComboSeries[], b: readonly ReportComboSeries[]): boolean => a.length === b.length && a.every((s, i) => s.type === b[i]?.type && s.secondary === b[i]?.secondary)

/** 현재 계열 설정이 어느 프리셋과 같은지(아니면 'custom'). */
export function comboPresetOf(current: readonly ReportComboSeries[]): ComboPreset['key'] | 'custom' {
  return COMBO_PRESETS.find((p) => same(current, p.apply(current.length)))?.key ?? 'custom'
}

/** 계열 설정이 없으면(서버가 채워 주는 옛 규칙과 같게) 첫 값은 막대, 나머지는 꺾은선이고 `secondaryAxis`이면 꺾은선이 보조 축이다. */
export function comboSeriesOf(input: ReportChartInput, count: number): ReportComboSeries[] {
  if (input.comboSeries && input.comboSeries.length === count) return input.comboSeries
  return Array.from({ length: count }, (_, i) => (i === 0 ? series('column') : series('line', input.secondaryAxis)))
}

const STACKED: readonly ReportComboSeriesType[] = ['stacked_column', 'stacked_area']
const isBar = (type: ReportComboSeriesType): boolean => type === 'column' || type === 'stacked_column'

/** Chart.js는 묶음 키를 `stack || type`으로 정한다. 누적이 아닌 계열은 계열마다 고유 id, 누적은 종류별 공통 id를 쓴다. */
function datasetOf(setting: ReportComboSeries, label: string, data: (number | null)[], i: number) {
  const c = color(i)
  const axisId = setting.secondary ? { yAxisID: 'y1' } : {}
  switch (setting.type) {
    case 'column':
      return { type: 'bar', label, data, backgroundColor: c, stack: `column-${i}`, order: 1, ...axisId }
    case 'stacked_column':
      return { type: 'bar', label, data, backgroundColor: c, stack: 'bars', order: 1, ...axisId }
    case 'area':
      return { type: 'line', label, data, borderColor: c, backgroundColor: withAlpha(c, 0x99), fill: 'origin', stack: `area-${i}`, pointRadius: 0, order: 2, ...axisId }
    case 'stacked_area':
      return { type: 'line', label, data, borderColor: c, backgroundColor: withAlpha(c, 0x99), fill: 'stack', stack: 'areas', pointRadius: 0, order: 2, ...axisId }
    default:
      return { type: 'line', label, data, borderColor: c, backgroundColor: c, fill: false, stack: `line-${i}`, pointRadius: setting.type === 'line_markers' ? 3 : 0, pointHoverRadius: 4, order: 0, ...axisId }
  }
}

/** 콤보: 값 열마다 계열 종류(막대·누적 막대·꺾은선·영역·누적 영역)와 보조 축을 따로 정한다. 꺾은선이 막대 위에 그려진다. */
export function buildCombo({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const grid = pivot(input, result, columns, fmt)
  const limit = tooMany(grid.labels.length * grid.sets.length)
  if (limit) return limit
  const settings = comboSeriesOf(input, grid.sets.length)
  // 누적이 아닌 종류는 막대·꺾은선·영역 모두 없는 칸을 0이 아니라 끊는다(꺾은선) / 0으로 채운다(막대).
  const datasets: Datasets = grid.sets.map((set, i) => {
    const setting = settings[i] ?? series('line')
    const gaps = !isBar(setting.type) && !STACKED.includes(setting.type)
    return datasetOf(setting, set.label, set.cells.map((cell) => cell?.value ?? (gaps ? null : 0)), i)
  })
  const stackedOn = (secondary: boolean): boolean => settings.some((s) => s.secondary === secondary && STACKED.includes(s.type))
  const stackedBar = settings.some((s) => s.type === 'stacked_column')
  const primary = columns.values.filter((_, i) => !settings[i]?.secondary)
  const secondary = columns.values.filter((_, i) => settings[i]?.secondary)
  const scales: NonNullable<ChartOptions['scales']> = {
    x: axis(input.categoryAxisTitle, stackedBar ? { stacked: true } : {}),
    y: axis(input.valueAxisTitle, { ...rangeOf(input, false), ...(stackedOn(false) ? { stacked: true } : {}) }, primary),
  }
  if (settings.some((s) => s.secondary)) {
    scales.y1 = secondaryAxis(stackedOn(true) ? { stacked: true } : {}, secondary) as never
  }
  const options: ChartOptions = baseOptions({ ...(settings.every((s) => isBar(s.type)) ? {} : NEAR_POINT), scales, plugins: pluginsOf(input, gridCallbacks(grid, fmt, null)) })
  return { type: 'bar', data: chartData(grid.labels, datasets), options, description: describe(kindLabel(input.kind), columns, columnHeader), notes: [] }
}
