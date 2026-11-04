import type { ChartData, ChartOptions, ChartType } from 'chart.js'
import type { ReportCell, ReportChartInput, ReportResult, ReportResultColumn } from '../../../../shared/model/reportTypes'
import { formatWonAxis } from '../../../../shared/model/money'
import { SERIES_COLORS, chartTheme } from '../../../../shared/ui/chartTheme'
import { formatCell, isWonColumn, type FormatContext } from '../../designer/format/formatCell'
import type { ChartKindRule } from '../chartKinds'
import type { ChartColumns, Pivot, PivotCell } from '../pivot'

export const CHART_MISMATCH = '차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요'
export const CHART_TOO_MANY = '범주가 너무 많아 차트를 그리지 않습니다(최대 1,000개). 조건을 좁히세요'

export interface BuiltChart {
  type: ChartType
  data: ChartData
  options: ChartOptions
  /** 그림의 접근성 이름에 쓰는 한 줄 설명. */
  description: string
  /** 그리지 않은 항목 수 같은 안내(차트 아래에 보인다). */
  notes: string[]
}

export type BuildOutcome = BuiltChart | { problem: string }

/** 빌더가 받는 입력: 설정, 결과, 설정이 가리키는 결과 열, 서식 맥락, 종류 규칙. */
export interface BuildInput {
  input: ReportChartInput
  result: ReportResult
  columns: ChartColumns
  fmt: FormatContext
  rule: ChartKindRule
}

export type Datasets = Record<string, unknown>[]

/** 데이터셋은 종류마다 모양이 달라(콤보는 데이터셋마다 type) Chart.js의 합집합 타입으로 좁힐 수 없어 한곳에서만 넘긴다. */
export const chartData = (labels: string[], datasets: Datasets): ChartData => ({ labels, datasets }) as unknown as ChartData

export const color = (i: number): string => SERIES_COLORS[i % SERIES_COLORS.length] ?? '#94a3b8'
export const fixed = (value: number): string => String(Number(value.toFixed(1)))

/** 색에 투명도(0~255)를 붙인다(`#rrggbbaa`). */
export const withAlpha = (hex: string, alpha: number): string => `${hex}${Math.round(alpha).toString(16).padStart(2, '0')}`

export const problem = (message: string): { problem: string } => ({ problem: message })
export const tooMany = (count: number): { problem: string } | null => (count > 1000 ? problem(CHART_TOO_MANY) : null)

/** 결과 셀을 표와 같은 글자로. 셀이 없으면 `—`. */
export const show = (cell: PivotCell | null, fmt: FormatContext): string => (cell ? formatCell(cell.raw, cell.column, fmt) : '—')
export const showValue = (value: ReportCell, column: ReportResultColumn, fmt: FormatContext): string => formatCell(value, column, fmt)

export function cellAt(grid: Pivot, datasetIndex: number, dataIndex: number): PivotCell | null {
  return grid.sets[datasetIndex]?.cells[dataIndex] ?? null
}

/** 값 축의 최소·최대. 100% 누적은 최대를 100으로 둔다. */
export function rangeOf(input: ReportChartInput, percent: boolean): Record<string, number> {
  return {
    ...(typeof input.valueMin === 'number' ? { min: input.valueMin } : {}),
    ...(typeof input.valueMax === 'number' ? { max: input.valueMax } : percent ? { max: 100 } : {}),
  }
}

/** 값 축에 올라간 값 열이 모두 금액이면 눈금을 억·만으로 줄인다(열이 없으면 줄이지 않는다). */
export function moneyTicks(values: readonly ReportResultColumn[]): { callback?: (v: string | number) => string } {
  return values.length > 0 && values.every(isWonColumn) ? { callback: (v) => formatWonAxis(Number(v)) } : {}
}

/** 축 하나의 공통 모양(제목·눈금·격자). */
export function axis(title: string, extra: Record<string, unknown> = {}, shown: readonly ReportResultColumn[] = []) {
  const theme = chartTheme()
  return {
    title: { display: title !== '', text: title, color: theme.text },
    ticks: { color: theme.text, ...moneyTicks(shown) },
    grid: { color: theme.grid },
    ...extra,
  }
}

/** 보조 축(오른쪽, 격자는 그리지 않는다). */
export function secondaryAxis(extra: Record<string, unknown> = {}, shown: readonly ReportResultColumn[] = []) {
  const theme = chartTheme()
  return { type: 'linear' as const, position: 'right' as const, grid: { drawOnChartArea: false, color: theme.grid }, ticks: { color: theme.text, ...moneyTicks(shown) }, ...extra }
}

interface Callbacks {
  tooltipLabel?: (c: never) => string | string[]
  tooltipTitle?: (items: never) => string | string[]
  dataLabel?: (value: unknown, c: never) => string
}

/** 제목·범례·툴팁·데이터 레이블이 들어 있는 `plugins`. 종류마다 다른 글자는 콜백으로 받는다. */
export function pluginsOf(input: ReportChartInput, cb: Callbacks, legend = true): NonNullable<ChartOptions['plugins']> {
  const theme = chartTheme()
  return {
    title: { display: input.title !== '', text: input.title, color: theme.text },
    legend: { display: legend && input.legend !== 'none', position: input.legend === 'none' ? 'top' : input.legend, labels: { color: theme.text } },
    tooltip: { callbacks: { ...(cb.tooltipLabel ? { label: cb.tooltipLabel } : {}), ...(cb.tooltipTitle ? { title: cb.tooltipTitle } : {}) } },
    datalabels: { display: input.dataLabels, color: theme.text, ...(cb.dataLabel ? { formatter: cb.dataLabel } : {}) },
  } as unknown as NonNullable<ChartOptions['plugins']>
}

export interface TipContext {
  datasetIndex: number
  dataIndex: number
  label: string
  dataset: { label?: string }
}

/** 범주(가로) 이름을 전체 이름으로 바꾸는 툴팁 제목. */
export const titleOf =
  (grid: Pivot) =>
  (items: readonly { dataIndex: number; label: string }[]): string => {
    const first = items[0]
    return first ? (grid.titles[first.dataIndex] ?? first.label) : ''
  }

export function describe(label: string, columns: ChartColumns, headers: (c: ReportResultColumn) => string): string {
  const values = columns.values.map(headers).join(', ')
  return `${label} 차트: ${headers(columns.category)} 기준 ${values}`
}

/** 표식이 없는 선·영역·방사형도 점 가까이에서 툴팁이 뜨게 한다(기본 상호작용은 점 위 1px 안에서만 적중). 분산형은 x가 같은 점이 없어 가장 가까운 점을 쓴다. */
export const NEAR_POINT = { interaction: { mode: 'index', intersect: false } } as const satisfies ChartOptions
export const NEAREST_POINT = { interaction: { mode: 'nearest', intersect: false } } as const satisfies ChartOptions

export const baseOptions = (extra: ChartOptions = {}): ChartOptions => ({ responsive: true, maintainAspectRatio: false, ...extra })

/** 숫자 칸의 값(없으면 null). */
export const numberAt = (cell: ReportCell | undefined): number | null => (typeof cell === 'number' ? cell : null)

/** 범주별 계열 합 대비 %(100% 누적). 합이 0인 범주는 0이다. */
export function sharesOf(grid: Pivot): number[][] {
  const sums = grid.labels.map((_, i) => grid.sets.reduce((sum, set) => sum + (set.cells[i]?.value ?? 0), 0))
  return grid.sets.map((set) => set.cells.map((cell, i) => (sums[i] ? ((cell?.value ?? 0) * 100) / (sums[i] ?? 1) : 0)))
}

/**
 * 범주 × 데이터셋 행렬 위의 툴팁·데이터 레이블 글자. 값은 결과 표와 같은 서식(`formatCell`)이다.
 * `shares`가 있으면(100% 누적) 퍼센트와 원래 값을 함께 쓴다. `byLabel`이면 툴팁 머리가 범주 이름(원·도넛)이다.
 */
export function gridCallbacks(grid: Pivot, fmt: FormatContext, shares: number[][] | null, byLabel = false) {
  return {
    tooltipLabel: (c: TipContext): string => {
      const cell = cellAt(grid, c.datasetIndex, c.dataIndex)
      const head = byLabel ? (grid.titles[c.dataIndex] ?? c.label) : (grid.sets[c.datasetIndex]?.title ?? c.dataset.label ?? '')
      if (!shares) return `${head}: ${show(cell, fmt)}`
      return `${head}: ${fixed(shares[c.datasetIndex]?.[c.dataIndex] ?? 0)}% (${show(cell, fmt)})`
    },
    tooltipTitle: titleOf(grid),
    dataLabel: (value: unknown, c: { datasetIndex: number; dataIndex: number }): string => {
      if (shares) return `${fixed(typeof value === 'number' ? value : 0)}%`
      return show(cellAt(grid, c.datasetIndex, c.dataIndex), fmt)
    },
  }
}
