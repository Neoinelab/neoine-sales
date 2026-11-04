import type { ChartOptions } from 'chart.js'
import type { ReportChartInput, ReportHistogramBins, ReportResult, ReportResultColumn } from '../../../../shared/model/reportTypes'
import { chartTheme } from '../../../../shared/ui/chartTheme'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { histogramBins } from '../compute/histogramBins'
import { paretoSeries } from '../compute/paretoSeries'
import { pivot } from '../pivot'
import {
  axis,
  baseOptions,
  cellAt,
  chartData,
  color,
  describe,
  fixed,
  numberAt,
  pluginsOf,
  problem,
  rangeOf,
  secondaryAxis,
  show,
  tooMany,
  type BuildInput,
  type BuildOutcome,
  type Datasets,
} from './common'

const AUTO: ReportHistogramBins = { binMode: 'auto', binCount: null, binWidth: null, overflow: null, underflow: null }

/** 구간 경계 숫자의 글자: 정수는 천 단위 구분, 소수는 최대 둘째 자리(표 서식은 소수를 반올림하지만 경계는 정확해야 읽힌다). */
const edgeText = (n: number): string => n.toLocaleString('en-US', { maximumFractionDigits: 2 })

/**
 * 히스토그램: 표본 = 값 열의 행마다 한 값(그룹핑 없는 결과는 행, 그룹핑한 결과는 그룹). 구간 이름이 가로축이고 높이가 개수다.
 * 한도는 표본 수가 아니라 구간 수에 적용한다.
 */
export function buildHistogram(input: ReportChartInput, result: ReportResult, value: ReportResultColumn): BuildOutcome {
  const bins = histogramBins(
    result.rows.map((row) => numberAt(row[value.index])),
    input.histogram ?? AUTO,
    edgeText,
  )
  // 1,000개를 넘는 구간은 구간 너비 방식에서만 나온다(자동·구간 수 방식은 최대 100개).
  if (bins.filter((b) => b.kind === 'range').length > 1000) return problem('구간이 너무 많아 차트를 그리지 않습니다(최대 1,000개). 구간 너비를 늘리세요')
  const theme = chartTheme()
  const dataset = { label: '빈도', data: bins.map((b) => b.count), backgroundColor: color(1), borderColor: theme.grid, borderWidth: 1, categoryPercentage: 1, barPercentage: 1 }
  const cb = {
    tooltipTitle: (items: readonly { dataIndex: number }[]): string => bins[items[0]?.dataIndex ?? -1]?.label ?? '',
    tooltipLabel: (c: { dataIndex: number }): string => `빈도: ${(bins[c.dataIndex]?.count ?? 0).toLocaleString('en-US')}`,
    dataLabel: (v: unknown): string => String(v),
  }
  const options: ChartOptions = baseOptions({
    scales: {
      x: axis(input.categoryAxisTitle),
      y: axis(input.valueAxisTitle, { beginAtZero: true, ...rangeOf(input, false), ticks: { color: theme.text, precision: 0 } }),
    },
    plugins: pluginsOf(input, cb, false),
  })
  return {
    type: 'bar',
    data: chartData(bins.map((b) => b.label), [dataset]),
    options,
    description: `${kindLabel(input.kind)} 차트: ${columnHeader(value)} 분포`,
    notes: [],
  }
}

/** 파레토: 값 내림차순 막대(리포트 정렬과 무관) + 누적 %를 보조 축(0~100%) 꺾은선으로. 0 이하·빈 값 항목은 빠진다. */
export function buildPareto({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const grid = pivot(input, result, columns, fmt)
  const limit = tooMany(grid.labels.length)
  if (limit) return limit
  const set = grid.sets[0]
  const pareto = paretoSeries(grid.labels, set ? set.cells.map((cell) => cell?.value ?? null) : [])
  const theme = chartTheme()
  const header = set?.label ?? ''
  const datasets: Datasets = [
    { type: 'bar', label: header, data: pareto.values, backgroundColor: color(0), yAxisID: 'y', order: 1 },
    { type: 'line', label: '누적 %', data: pareto.cumulative, borderColor: color(1), backgroundColor: color(1), yAxisID: 'y1', order: 0, fill: false, pointRadius: 3 },
  ]
  const cell = (dataIndex: number) => cellAt(grid, 0, pareto.indices[dataIndex] ?? -1)
  const cb = {
    tooltipTitle: (items: readonly { dataIndex: number }[]): string => grid.titles[pareto.indices[items[0]?.dataIndex ?? -1] ?? -1] ?? '',
    tooltipLabel: (c: { datasetIndex: number; dataIndex: number }): string =>
      c.datasetIndex === 0 ? `${header}: ${show(cell(c.dataIndex), fmt)}` : `누적 %: ${fixed(pareto.cumulative[c.dataIndex] ?? 0)}%`,
    dataLabel: (_value: unknown, c: { datasetIndex: number; dataIndex: number }): string =>
      c.datasetIndex === 0 ? show(cell(c.dataIndex), fmt) : `${fixed(pareto.cumulative[c.dataIndex] ?? 0)}%`,
  }
  const options: ChartOptions = baseOptions({
    scales: {
      x: axis(input.categoryAxisTitle),
      y: axis(input.valueAxisTitle, rangeOf(input, false), columns.values),
      y1: secondaryAxis({ min: 0, max: 100, ticks: { color: theme.text, callback: (v: string | number) => `${v}%` } }),
    },
    plugins: pluginsOf(input, cb),
  })
  const notes = pareto.skipped > 0 ? [`값이 0 이하이거나 빈 항목 ${pareto.skipped}개는 그리지 않았습니다`] : []
  return { type: 'bar', data: chartData(pareto.labels, datasets), options, description: describe(kindLabel(input.kind), columns, columnHeader), notes }
}
