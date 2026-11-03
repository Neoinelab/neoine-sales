import type { ChartOptions } from 'chart.js'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { funnelBars } from '../compute/funnelBars'
import { pivot } from '../pivot'
import { axis, baseOptions, chartData, color, describe, pluginsOf, show, cellAt, tooMany, type BuildInput, type BuildOutcome } from './common'

/** 깔때기: 결과 행 순서대로 위에서 아래로 가운데 정렬 가로 막대(플러그인 없음). 값 축은 숨기고 0 이하·빈 값 항목은 뺀다. */
export function buildFunnel({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const grid = pivot(input, result, columns, fmt)
  const limit = tooMany(grid.labels.length)
  if (limit) return limit
  const set = grid.sets[0]
  const { bars, skipped } = funnelBars(set ? set.cells.map((cell) => cell?.value ?? null) : [])
  const widest = Math.max(0, ...bars.map((b) => b.value)) / 2
  const header = set?.label ?? ''
  const dataset = { label: header, data: bars.map((b) => b.range), backgroundColor: bars.map((_, i) => color(i)), categoryPercentage: 0.9, barPercentage: 1 }
  const cell = (dataIndex: number) => cellAt(grid, 0, bars[dataIndex]?.index ?? -1)
  const cb = {
    tooltipTitle: (items: readonly { dataIndex: number }[]): string => grid.titles[bars[items[0]?.dataIndex ?? -1]?.index ?? -1] ?? '',
    tooltipLabel: (c: { dataIndex: number }): string => `${header}: ${show(cell(c.dataIndex), fmt)}`,
    dataLabel: (_value: unknown, c: { dataIndex: number }): string => show(cell(c.dataIndex), fmt),
  }
  const options: ChartOptions = baseOptions({
    indexAxis: 'y',
    scales: {
      y: axis(input.categoryAxisTitle, { grid: { display: false } }),
      x: { display: false, min: -widest, max: widest },
    },
    plugins: pluginsOf(input, cb, false),
  })
  const notes = skipped > 0 ? [`값이 0 이하이거나 빈 항목 ${skipped}개는 그리지 않았습니다`] : []
  return {
    type: 'bar',
    data: chartData(bars.map((b) => grid.labels[b.index] ?? ''), [dataset]),
    options,
    description: describe(kindLabel(input.kind), columns, columnHeader),
    notes,
  }
}
