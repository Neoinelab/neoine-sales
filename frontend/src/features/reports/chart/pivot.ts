import type { ReportCell, ReportChartInput, ReportResult, ReportResultColumn } from '../../../shared/model/reportTypes'
import { columnHeader, formatCell, isNumericColumn, type FormatContext } from '../designer/format/formatCell'
import { kindRule } from './chartKinds'

const NONE_LABEL = '(없음)'
const THOUSAND = 1000
const MILLION = 1_000_000

/** 차트 칸 하나: 결과 셀 원본, 그 열, 차트에 쓰는 값(단위 변환 뒤). 값이 없으면 null. */
export interface PivotCell {
  raw: ReportCell
  column: ReportResultColumn
  value: number | null
}

export interface PivotSet {
  label: string
  cells: (PivotCell | null)[]
}

/** 결과 행을 범주(가로) × 데이터셋(계열 또는 값 열) 행렬로 옮긴 것. */
export interface Pivot {
  labels: string[]
  sets: PivotSet[]
}

/** 설정이 가리키는 결과 열. 결과와 맞지 않으면 null. */
export interface ChartColumns {
  category: ReportResultColumn
  series: ReportResultColumn | null
  values: ReportResultColumn[]
}

/** 값 = 셀 값. 천원 포맷은 ÷1,000, 백만원 포맷은 ÷1,000,000, 그 밖은 그대로. */
export function unitDivisor(column: ReportResultColumn): number {
  if (column.format === 'krw_thousand') return THOUSAND
  return column.format === 'krw_million' ? MILLION : 1
}

export function cellOf(raw: ReportCell, column: ReportResultColumn): PivotCell {
  return { raw, column, value: typeof raw === 'number' ? raw / unitDivisor(column) : null }
}

export const nameOf = (cell: ReportCell, column: ReportResultColumn, ctx: FormatContext): string => (cell === null ? NONE_LABEL : formatCell(cell, column, ctx))

/** 설정(index)을 결과 열로 풀고 규칙(그룹 열·숫자 열·개수)을 확인한다. 어긋나면 null. */
export function resolveColumns(input: ReportChartInput, result: ReportResult): ChartColumns | null {
  const rule = kindRule(input.kind)
  const column = (index: number | null): ReportResultColumn | undefined => (index === null ? undefined : result.columns.find((c) => c.index === index))
  const category = column(input.category)
  if (!category?.group) return null
  let series: ReportResultColumn | null = null
  if (input.series !== null) {
    const found = column(input.series)
    if (!rule.allowsSeries || !found?.group || found.index === category.index) return null
    series = found
  }
  const values: ReportResultColumn[] = []
  for (const index of input.values) {
    const found = column(index)
    if (!found || found.group || !isNumericColumn(found)) return null
    values.push(found)
  }
  const [min, max] = series ? [1, 1] : [rule.valuesMin, rule.valuesMax]
  if (values.length < min || values.length > max) return null
  return { category, series, values }
}

/** 값을 가진 첫 등장 순서로 번호를 매기는 작은 도구(null도 하나의 값). */
function indexer(): { of: (cell: ReportCell) => number; keys: ReportCell[] } {
  const map = new Map<ReportCell, number>()
  const keys: ReportCell[] = []
  return {
    keys,
    of: (cell) => {
      const found = map.get(cell)
      if (found !== undefined) return found
      map.set(cell, keys.length)
      keys.push(cell)
      return keys.length - 1
    },
  }
}

const columnHeaderAt = (columns: ChartColumns, j: number): string => {
  const column = columns.values[j]
  return column ? columnHeader(column) : ''
}

/** 결과 행 → 행렬. 범주·계열은 결과 행 순서의 첫 등장 순이다. 행/열 전환(swap)은 규칙이 허용할 때 가로·데이터셋을 맞바꾼다. */
export function pivot(input: ReportChartInput, result: ReportResult, columns: ChartColumns, ctx: FormatContext): Pivot {
  const categories = indexer()
  const seriesKeys = indexer()
  const first = columns.values[0]
  const sets: PivotSet[] = columns.values.map(() => ({ label: '', cells: [] }))
  const seriesSets: PivotSet[] = []
  for (const row of result.rows) {
    const at = categories.of(row[columns.category.index] ?? null)
    if (columns.series && first) {
      const si = seriesKeys.of(row[columns.series.index] ?? null)
      seriesSets[si] ??= { label: nameOf(seriesKeys.keys[si] ?? null, columns.series, ctx), cells: [] }
      const target = seriesSets[si]
      if (target) target.cells[at] = cellOf(row[first.index] ?? null, first)
    } else {
      columns.values.forEach((column, j) => {
        const target = sets[j]
        if (target) target.cells[at] = cellOf(row[column.index] ?? null, column)
      })
    }
  }
  const labels = categories.keys.map((key) => nameOf(key, columns.category, ctx))
  const base = columns.series ? seriesSets : sets
  const filled = base.map((set, j) => ({ label: columns.series ? set.label : columnHeaderAt(columns, j), cells: Array.from({ length: labels.length }, (_, i) => set.cells[i] ?? null) }))
  if (!(input.swap && kindRule(input.kind).allowsSwap)) return { labels, sets: filled }
  return {
    labels: filled.map((set) => set.label),
    sets: labels.map((label, i) => ({ label, cells: filled.map((set) => set.cells[i] ?? null) })),
  }
}
