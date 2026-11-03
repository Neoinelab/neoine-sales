import type { ChartOptions } from 'chart.js'
import type { ReportChartKind } from '../../../../shared/model/reportTypes'
import { chartTheme } from '../../../../shared/ui/chartTheme'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { pivot } from '../pivot'
import { axis, baseOptions, chartData, color, describe, gridCallbacks, pluginsOf, rangeOf, sharesOf, tooMany, withAlpha, type BuildInput, type BuildOutcome, type Datasets } from './common'

/** 막대·꺾은선·영역 종류의 모양: 가로/세로, 누적, 100% 누적, 표식. 이름 규칙으로 정한다(`stacked_100_horizontal_bar` 등). */
interface Shape {
  style: 'bar' | 'line' | 'area'
  horizontal: boolean
  stacked: boolean
  percent: boolean
  markers: boolean
}

const BAR_LINE_AREA: readonly ReportChartKind[] = [
  'bar',
  'stacked_bar',
  'stacked_100_bar',
  'horizontal_bar',
  'stacked_horizontal_bar',
  'stacked_100_horizontal_bar',
  'line',
  'line_markers',
  'stacked_line',
  'stacked_line_markers',
  'stacked_100_line',
  'stacked_100_line_markers',
  'area',
  'stacked_area',
  'stacked_100_area',
]

export const isCartesianKind = (kind: ReportChartKind): boolean => BAR_LINE_AREA.includes(kind)

function shapeOf(kind: ReportChartKind): Shape {
  return {
    style: kind.endsWith('area') ? 'area' : kind.includes('line') ? 'line' : 'bar',
    horizontal: kind.includes('horizontal'),
    stacked: kind.startsWith('stacked'),
    percent: kind.startsWith('stacked_100'),
    markers: kind.endsWith('_markers'),
  }
}

const MARKER_RADIUS = 3

function datasetOf(shape: Shape, label: string, data: (number | null)[], i: number) {
  const c = color(i)
  if (shape.style === 'bar') return { label, data, backgroundColor: c }
  if (shape.style === 'line') {
    return { label, data, borderColor: c, backgroundColor: c, fill: false, pointRadius: shape.markers ? MARKER_RADIUS : 0, pointHoverRadius: 4, ...(shape.stacked ? { stack: 'lines' } : {}) }
  }
  return { label, data, borderColor: c, backgroundColor: withAlpha(c, 0x99), fill: shape.stacked ? 'stack' : 'origin', pointRadius: 0, pointHoverRadius: 4, ...(shape.stacked ? { stack: 'areas' } : {}) }
}

/** 막대·꺾은선·영역 계열(묶은·누적·100% 누적, 세로·가로). 꺾은선·영역은 누적이 아닐 때만 없는 칸을 끊고(null), 나머지는 0으로 채운다. */
export function buildCartesian({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const shape = shapeOf(input.kind)
  const grid = pivot(input, result, columns, fmt)
  const limit = tooMany(grid.labels.length * grid.sets.length)
  if (limit) return limit
  const shares = shape.percent ? sharesOf(grid) : null
  const gaps = shape.style !== 'bar' && !shape.stacked
  const datasets: Datasets = grid.sets.map((set, i) =>
    datasetOf(shape, set.label, shares ? (shares[i] ?? []) : set.cells.map((cell) => cell?.value ?? (gaps ? null : 0)), i),
  )
  const theme = chartTheme()
  const stackedValue = shape.stacked ? { stacked: true } : {}
  const category = axis(input.categoryAxisTitle, shape.stacked && shape.style === 'bar' ? { stacked: true } : {})
  const value = axis(
    input.valueAxisTitle,
    { ...rangeOf(input, shape.percent), ...stackedValue, ...(shape.percent ? { ticks: { color: theme.text, callback: (v: string | number) => `${v}%` } } : {}) },
    shape.percent ? [] : columns.values,
  )
  const cb = gridCallbacks(grid, fmt, shares)
  const options: ChartOptions = baseOptions({
    ...(shape.horizontal ? { indexAxis: 'y' as const } : {}),
    scales: shape.horizontal ? { y: category, x: value } : { x: category, y: value },
    plugins: pluginsOf(input, cb),
  })
  return {
    type: shape.style === 'bar' ? 'bar' : 'line',
    data: chartData(grid.labels, datasets),
    options,
    description: describe(kindLabel(input.kind), columns, columnHeader),
    notes: [],
  }
}
