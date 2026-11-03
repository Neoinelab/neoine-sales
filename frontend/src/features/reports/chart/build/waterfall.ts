import type { ChartOptions } from 'chart.js'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { waterfallSteps, type WaterfallStep } from '../compute/waterfallSteps'
import { pivot } from '../pivot'
import { axis, baseOptions, chartData, describe, pluginsOf, rangeOf, showValue, tooMany, type BuildInput, type BuildOutcome } from './common'

export const TOTAL_LABEL = '합계'
const KINDS = [
  { kind: 'increase', label: '증가', color: '#34d399' },
  { kind: 'decrease', label: '감소', color: '#f87171' },
  { kind: 'total', label: TOTAL_LABEL, color: '#94a3b8' },
] as const

/** 폭포: 결과 행 순서대로 앞 누계에서 시작하는 뜬 막대. 증가·감소(·합계)를 색과 범례로 구분하고 빈 값은 0이다. */
export function buildWaterfall({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const grid = pivot(input, result, columns, fmt)
  const limit = tooMany(grid.labels.length)
  if (limit) return limit
  const set = grid.sets[0]
  const steps: WaterfallStep[] = waterfallSteps(set ? set.cells.map((cell) => cell?.value ?? null) : [], input.showTotal)
  const labels = input.showTotal ? [...grid.labels, TOTAL_LABEL] : grid.labels
  const titles = input.showTotal ? [...grid.titles, TOTAL_LABEL] : grid.titles
  const unit = columns.values[0]
  const kinds = KINDS.filter((k) => k.kind !== 'total' || input.showTotal)
  const datasets = kinds.map((k) => ({
    label: k.label,
    data: steps.map((s) => (s.kind === k.kind ? [s.from, s.to] : null)),
    backgroundColor: k.color,
    grouped: false,
    barPercentage: 0.8,
  }))
  // 증가·감소 막대는 변화량(끝 − 시작), 합계 막대는 누계를 보인다.
  const amount = (i: number): string => {
    const step = steps[i]
    if (!step || !unit) return '—'
    return showValue(step.kind === 'total' ? step.to : step.to - step.from, unit, fmt)
  }
  const cb = {
    tooltipTitle: (items: readonly { dataIndex: number }[]): string => titles[items[0]?.dataIndex ?? -1] ?? '',
    tooltipLabel: (c: { dataset: { label?: string }; dataIndex: number }): string => `${c.dataset.label ?? ''}: ${amount(c.dataIndex)}`,
    dataLabel: (_value: unknown, c: { dataIndex: number }): string => amount(c.dataIndex),
  }
  const options: ChartOptions = baseOptions({
    scales: { x: axis(input.categoryAxisTitle), y: axis(input.valueAxisTitle, rangeOf(input, false), columns.values) },
    plugins: pluginsOf(input, cb),
  })
  return { type: 'bar', data: chartData(labels, datasets), options, description: describe(kindLabel(input.kind), columns, columnHeader), notes: [] }
}
