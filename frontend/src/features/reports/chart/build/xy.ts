import type { ChartOptions } from 'chart.js'
import type { ReportChartKind } from '../../../../shared/model/reportTypes'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { bubbleRadius } from '../compute/bubbleRadius'
import { cellOf, nameOf, type PivotCell } from '../pivot'
import { CHART_TOO_MANY, axis, baseOptions, chartData, color, describe, numberAt, pluginsOf, problem, rangeOf, show, type BuildInput, type BuildOutcome, type Datasets } from './common'

interface Style {
  line: boolean
  smooth: boolean
  markers: boolean
}

/** 분산형 5종의 선·곡선·표식. */
const STYLES: Partial<Record<ReportChartKind, Style>> = {
  scatter: { line: false, smooth: false, markers: true },
  scatter_smooth_markers: { line: true, smooth: true, markers: true },
  scatter_smooth: { line: true, smooth: true, markers: false },
  scatter_line_markers: { line: true, smooth: false, markers: true },
  scatter_line: { line: true, smooth: false, markers: false },
}

const MARKER_RADIUS = 3
const SMOOTH = 0.4

interface Plotted {
  names: string[]
  points: { x: number; y: number }[]
  infos: { x: PivotCell; y: PivotCell }[]
}

/** 가로는 첫째 값, 세로는 나머지 값 열마다 한 계열. 점마다 결과 행 하나(점 이름 = 범주). X·Y 중 빈 값이 있는 행은 그 계열에서 빠진다. */
function plot(input: BuildInput, yIndex: number): Plotted {
  const { result, columns, fmt } = input
  const xColumn = columns.values[0]
  const yColumn = columns.values[yIndex]
  const out: Plotted = { names: [], points: [], infos: [] }
  if (!xColumn || !yColumn) return out
  for (const row of result.rows) {
    const x = cellOf(row[xColumn.index] ?? null, xColumn)
    const y = cellOf(row[yColumn.index] ?? null, yColumn)
    if (x.value === null || y.value === null) continue
    out.names.push(nameOf(row[columns.category.index] ?? null, columns.category, fmt))
    out.points.push({ x: x.value, y: y.value })
    out.infos.push({ x, y })
  }
  return out
}

/** 분산형(표식만·직선·곡선 5종). */
export function buildScatter(build: BuildInput): BuildOutcome {
  const { input, result, columns, fmt } = build
  const style = STYLES[input.kind] ?? STYLES.scatter!
  if (result.rows.length * (columns.values.length - 1) > 1000) return problem(CHART_TOO_MANY)
  const plotted = columns.values.slice(1).map((_, i) => plot(build, i + 1))
  const datasets: Datasets = plotted.map((p, i) => ({
    label: columnHeader(columns.values[i + 1]!),
    data: p.points,
    backgroundColor: color(i),
    borderColor: color(i),
    showLine: style.line,
    pointRadius: style.markers ? MARKER_RADIUS : 0,
    pointHoverRadius: 5,
    ...(style.smooth ? { tension: SMOOTH } : {}),
  }))
  const where = (c: { datasetIndex: number; dataIndex: number }) => plotted[c.datasetIndex]
  const cb = {
    tooltipLabel: (c: { datasetIndex: number; dataIndex: number }): string => {
      const p = where(c)
      const info = p?.infos[c.dataIndex]
      return `${p?.names[c.dataIndex] ?? ''}: (${info ? show(info.x, fmt) : '—'}, ${info ? show(info.y, fmt) : '—'})`
    },
    dataLabel: (_value: unknown, c: { datasetIndex: number; dataIndex: number }): string => show(where(c)?.infos[c.dataIndex]?.y ?? null, fmt),
  }
  const options: ChartOptions = baseOptions({
    scales: {
      x: axis(input.categoryAxisTitle, { type: 'linear' }, columns.values.slice(0, 1)),
      y: axis(input.valueAxisTitle, rangeOf(input, false), columns.values.slice(1)),
    },
    plugins: pluginsOf(input, cb),
  })
  return { type: 'scatter', data: chartData(plotted[0]?.names ?? [], datasets), options, description: describe(kindLabel(input.kind), columns, columnHeader), notes: [] }
}

/** 거품형: 값 열 3개(X, Y, 크기). 거품 면적이 크기에 비례하고, 크기가 0 이하이거나 빈 점은 그리지 않는다. */
export function buildBubble({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const [xColumn, yColumn, sizeColumn] = columns.values
  if (!xColumn || !yColumn || !sizeColumn) return problem('거품형은 값 열 3개(X, Y, 크기)가 필요합니다')
  if (result.rows.length > 1000) return problem(CHART_TOO_MANY)
  const rows = result.rows.flatMap((row) => {
    const x = cellOf(row[xColumn.index] ?? null, xColumn)
    const y = cellOf(row[yColumn.index] ?? null, yColumn)
    if (x.value === null || y.value === null) return []
    return [{ name: nameOf(row[columns.category.index] ?? null, columns.category, fmt), x, y, size: cellOf(row[sizeColumn.index] ?? null, sizeColumn) }]
  })
  const { radii, skipped } = bubbleRadius(rows.map((r) => numberAt(r.size.raw)))
  const drawn = rows.flatMap((r, i) => {
    const radius = radii[i]
    return radius === null || radius === undefined ? [] : [{ ...r, point: { x: r.x.value ?? 0, y: r.y.value ?? 0, r: radius } }]
  })
  const dataset = { label: columnHeader(sizeColumn), data: drawn.map((d) => d.point), backgroundColor: `${color(0)}b3`, borderColor: color(0) }
  const cb = {
    tooltipLabel: (c: { dataIndex: number }): string => {
      const d = drawn[c.dataIndex]
      return d ? `${d.name}: (${show(d.x, fmt)}, ${show(d.y, fmt)}, ${show(d.size, fmt)})` : ''
    },
    dataLabel: (_value: unknown, c: { dataIndex: number }): string => show(drawn[c.dataIndex]?.size ?? null, fmt),
  }
  const options: ChartOptions = baseOptions({
    scales: {
      x: axis(input.categoryAxisTitle, { type: 'linear' }, [xColumn]),
      y: axis(input.valueAxisTitle, rangeOf(input, false), [yColumn]),
    },
    plugins: pluginsOf(input, cb),
  })
  const notes = skipped > 0 ? [`크기가 0 이하이거나 빈 값인 점 ${skipped}개는 그리지 않았습니다`] : []
  return { type: 'bubble', data: chartData(drawn.map((d) => d.name), [dataset]), options, description: describe(kindLabel(input.kind), columns, columnHeader), notes }
}
