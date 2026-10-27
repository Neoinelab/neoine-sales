import type { ChartData, ChartOptions, ChartType } from 'chart.js'
import type { ReportChartInput, ReportResult } from '../../../shared/model/reportTypes'
import { SERIES_COLORS, chartTheme } from '../../../shared/ui/chartTheme'
import { columnHeader, formatCell, type FormatContext } from '../designer/format/formatCell'
import { CHART_POINTS_MAX, kindLabel, kindRule } from './chartKinds'
import { cellOf, nameOf, pivot, resolveColumns, type ChartColumns, type Pivot, type PivotCell } from './pivot'

export const CHART_MISMATCH = '차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요'
export const CHART_TOO_MANY = '범주가 너무 많아 차트를 그리지 않습니다(최대 1,000개). 조건을 좁히세요'

export interface BuiltChart {
  type: ChartType
  data: ChartData
  options: ChartOptions
  /** 그림의 접근성 이름에 쓰는 한 줄 설명. */
  description: string
}

type Datasets = Record<string, unknown>[]

/** 데이터셋은 종류마다 모양이 달라(콤보는 데이터셋마다 type) Chart.js의 합집합 타입으로 좁힐 수 없어 한곳에서만 넘긴다. */
const chartData = (labels: string[], datasets: Datasets): ChartData => ({ labels, datasets }) as unknown as ChartData

const color = (i: number): string => SERIES_COLORS[i % SERIES_COLORS.length] ?? '#94a3b8'
const fixed = (value: number): string => String(Number(value.toFixed(1)))

interface Parts {
  input: ReportChartInput
  columns: ChartColumns
  grid: Pivot
  ctx: FormatContext
  /** 100% 누적일 때 범주마다 계열 합 대비 %로 바꾼 값. */
  percent: boolean
}

function cellAt(grid: Pivot, datasetIndex: number, dataIndex: number): PivotCell | null {
  return grid.sets[datasetIndex]?.cells[dataIndex] ?? null
}

/** 선·영역은 없는 칸을 끊고(null), 막대·누적·원은 0으로 채운다. */
const keepsGaps = (kind: ReportChartInput['kind']): boolean => kind === 'line' || kind === 'area'

function numbers(grid: Pivot, input: ReportChartInput, percent: boolean): (number | null)[][] {
  const columnSums = grid.labels.map((_, i) => grid.sets.reduce((sum, set) => sum + (set.cells[i]?.value ?? 0), 0))
  return grid.sets.map((set) =>
    set.cells.map((cell, i) => {
      if (percent) return columnSums[i] ? ((cell?.value ?? 0) * 100) / (columnSums[i] ?? 1) : 0
      return cell?.value ?? (keepsGaps(input.kind) ? null : 0)
    }),
  )
}

function datasetsOf(parts: Parts): Datasets {
  const { input, grid, percent } = parts
  const data = numbers(grid, input, percent)
  const kind = input.kind
  return grid.sets.map((set, i) => {
    const base = { label: set.label, data: data[i] }
    switch (kind) {
      case 'line':
        return { ...base, borderColor: color(i), backgroundColor: color(i), fill: false }
      case 'area':
        return { ...base, borderColor: color(i), backgroundColor: `${color(i)}99`, fill: 'origin' }
      case 'combo': {
        const line = i > 0
        return {
          ...base,
          type: line ? 'line' : 'bar',
          order: line ? 0 : 1,
          borderColor: color(i),
          backgroundColor: color(i),
          ...(line && input.secondaryAxis ? { yAxisID: 'y1' } : {}),
        }
      }
      default:
        return { ...base, backgroundColor: color(i) }
    }
  })
}

function pieDatasets(parts: Parts): { labels: string[]; datasets: Datasets } {
  const set = parts.grid.sets[0]
  const labels = parts.grid.labels
  return {
    labels,
    datasets: [{ label: set?.label ?? '', data: labels.map((_, i) => set?.cells[i]?.value ?? 0), backgroundColor: labels.map((_, i) => color(i)) }],
  }
}

/** 분산형: 점마다 결과 행 하나. 가로 = 첫째 값, 세로 = 둘째 값, 점 이름 = 범주. 값이 빈 행은 그리지 않는다. */
function scatter(result: ReportResult, columns: ChartColumns, ctx: FormatContext) {
  const [xColumn, yColumn] = columns.values
  const labels: string[] = []
  const points: { x: number; y: number }[] = []
  const infos: { x: PivotCell; y: PivotCell }[] = []
  if (!xColumn || !yColumn) return { labels, points, infos }
  for (const row of result.rows) {
    const x = cellOf(row[xColumn.index] ?? null, xColumn)
    const y = cellOf(row[yColumn.index] ?? null, yColumn)
    if (x.value === null || y.value === null) continue
    labels.push(nameOf(row[columns.category.index] ?? null, columns.category, ctx))
    points.push({ x: x.value, y: y.value })
    infos.push({ x, y })
  }
  return { labels, points, infos }
}

function rangeOf(input: ReportChartInput, percent: boolean): Record<string, number> {
  return {
    ...(typeof input.valueMin === 'number' ? { min: input.valueMin } : {}),
    ...(typeof input.valueMax === 'number' ? { max: input.valueMax } : percent ? { max: 100 } : {}),
  }
}

function scalesOf(input: ReportChartInput, percent: boolean): ChartOptions['scales'] | undefined {
  const theme = chartTheme()
  const axis = (title: string, extra: Record<string, unknown> = {}) => ({
    title: { display: title !== '', text: title, color: theme.text },
    ticks: { color: theme.text },
    grid: { color: theme.grid },
    ...extra,
  })
  const kind = input.kind
  if (kind === 'pie' || kind === 'doughnut') return undefined
  if (kind === 'scatter') return { x: axis(input.categoryAxisTitle, { type: 'linear' }), y: axis(input.valueAxisTitle, rangeOf(input, false)) }
  const stacked = kind === 'stacked_bar' || kind === 'stacked_100_bar'
  const horizontal = kind === 'horizontal_bar'
  const valueExtra = { ...rangeOf(input, percent), ...(stacked ? { stacked: true } : {}), ...(percent ? { ticks: { color: theme.text, callback: (v: string | number) => `${v}%` } } : {}) }
  const category = axis(input.categoryAxisTitle, stacked ? { stacked: true } : {})
  const value = axis(input.valueAxisTitle, valueExtra)
  const scales: NonNullable<ChartOptions['scales']> = horizontal ? { y: category, x: value } : { x: category, y: value }
  if (kind === 'combo' && input.secondaryAxis) {
    scales.y1 = { type: 'linear', position: 'right', grid: { drawOnChartArea: false, color: theme.grid }, ticks: { color: theme.text } }
  }
  return scales
}

interface TipContext {
  datasetIndex: number
  dataIndex: number
  label: string
  dataset: { label?: string }
}

/** 툴팁·데이터 레이블 글자. 값은 결과 표와 같은 서식(`formatCell`)으로 쓴다. */
function texts(parts: Parts, scatterInfos: { x: PivotCell; y: PivotCell }[] | null) {
  const { ctx, grid, percent } = parts
  const show = (cell: PivotCell | null): string => (cell ? formatCell(cell.raw, cell.column, ctx) : '—')
  const pie = parts.input.kind === 'pie' || parts.input.kind === 'doughnut'
  return {
    tooltip: (c: TipContext): string => {
      if (scatterInfos) {
        const info = scatterInfos[c.dataIndex]
        return `${c.label}: (${info ? show(info.x) : '—'}, ${info ? show(info.y) : '—'})`
      }
      const cell = cellAt(grid, c.datasetIndex, c.dataIndex)
      const head = pie ? c.label : (c.dataset.label ?? '')
      if (!percent) return `${head}: ${show(cell)}`
      const shares = numbers(grid, parts.input, true)
      return `${head}: ${fixed(shares[c.datasetIndex]?.[c.dataIndex] ?? 0)}% (${show(cell)})`
    },
    label: (value: unknown, c: { datasetIndex: number; dataIndex: number }): string => {
      if (scatterInfos) return show(scatterInfos[c.dataIndex]?.y ?? null)
      if (percent) return `${fixed(typeof value === 'number' ? value : 0)}%`
      return show(cellAt(grid, c.datasetIndex, c.dataIndex))
    },
  }
}

function optionsOf(parts: Parts, scatterInfos: { x: PivotCell; y: PivotCell }[] | null): ChartOptions {
  const { input, percent } = parts
  const theme = chartTheme()
  const text = texts(parts, scatterInfos)
  const scales = scalesOf(input, percent)
  return {
    responsive: true,
    maintainAspectRatio: false,
    ...(input.kind === 'horizontal_bar' ? { indexAxis: 'y' as const } : {}),
    ...(scales ? { scales } : {}),
    plugins: {
      title: { display: input.title !== '', text: input.title, color: theme.text },
      legend: { display: input.legend !== 'none', position: input.legend === 'none' ? 'top' : input.legend, labels: { color: theme.text } },
      tooltip: { callbacks: { label: text.tooltip } },
      datalabels: { display: input.dataLabels, color: theme.text, formatter: text.label },
    },
  }
}

function describe(input: ReportChartInput, columns: ChartColumns): string {
  const values = columns.values.map(columnHeader).join(', ')
  return `${kindLabel(input.kind)} 차트: ${columnHeader(columns.category)} 기준 ${values}`
}

const TYPES: Record<ReportChartInput['kind'], ChartType> = {
  bar: 'bar',
  horizontal_bar: 'bar',
  stacked_bar: 'bar',
  stacked_100_bar: 'bar',
  line: 'line',
  area: 'line',
  pie: 'pie',
  doughnut: 'doughnut',
  scatter: 'scatter',
  combo: 'bar',
}

/**
 * 차트 설정(컬럼은 결과 열 index) + 조회 결과 → Chart.js에 넘길 `type`·`data`·`options`.
 * 설정이 결과와 맞지 않거나 점이 1,000개를 넘으면 `{ problem }`을 돌려준다(틀린 차트를 그리지 않는다).
 */
export function buildChart(input: ReportChartInput, result: ReportResult, ctx: FormatContext): BuiltChart | { problem: string } {
  const columns = resolveColumns(input, result)
  if (!columns) return { problem: CHART_MISMATCH }
  const rule = kindRule(input.kind)
  const percent = rule.percentAxis
  const description = describe(input, columns)
  if (input.kind === 'scatter') {
    if (result.rows.length > CHART_POINTS_MAX) return { problem: CHART_TOO_MANY }
    const plotted = scatter(result, columns, ctx)
    const parts: Parts = { input, columns, grid: { labels: plotted.labels, sets: [] }, ctx, percent }
    const yColumn = columns.values[1]
    const data = chartData(plotted.labels, [{ label: yColumn ? columnHeader(yColumn) : '', data: plotted.points, backgroundColor: color(0) }])
    return { type: 'scatter', data, options: optionsOf(parts, plotted.infos), description }
  }
  const grid = pivot(input, result, columns, ctx)
  if (grid.labels.length * grid.sets.length > CHART_POINTS_MAX) return { problem: CHART_TOO_MANY }
  const parts: Parts = { input, columns, grid, ctx, percent }
  if (input.kind === 'pie' || input.kind === 'doughnut') {
    const pie = pieDatasets(parts)
    return { type: TYPES[input.kind], data: chartData(pie.labels, pie.datasets), options: optionsOf(parts, null), description }
  }
  return { type: TYPES[input.kind], data: chartData(grid.labels, datasetsOf(parts)), options: optionsOf(parts, null), description }
}
