import type { ChartOptions } from 'chart.js'
import { chartTheme } from '../../../../shared/ui/chartTheme'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { pivot } from '../pivot'
import { baseOptions, chartData, color, describe, gridCallbacks, moneyTicks, pluginsOf, problem, rangeOf, tooMany, withAlpha, type BuildInput, type BuildOutcome } from './common'

export const RADAR_MIN_CATEGORIES = 3
export const RADAR_TOO_FEW = '방사형은 범주가 3개 이상일 때 그립니다'

/** 방사형 3종(기본·표식·채워진): 범주가 축(꼭짓점), 계열(또는 값 열)마다 한 선. */
export function buildRadar({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const grid = pivot(input, result, columns, fmt)
  // 범주가 3개 미만이면 꼭짓점이 모자라 그리지 않는다.
  if (grid.labels.length < RADAR_MIN_CATEGORIES) return problem(RADAR_TOO_FEW)
  const limit = tooMany(grid.labels.length * grid.sets.length)
  if (limit) return limit
  const filled = input.kind === 'radar_filled'
  const markers = input.kind === 'radar_markers'
  const datasets = grid.sets.map((set, i) => ({
    label: set.label,
    data: set.cells.map((cell) => cell?.value ?? 0),
    borderColor: color(i),
    backgroundColor: filled ? withAlpha(color(i), 0x55) : color(i),
    fill: filled,
    pointRadius: markers ? 3 : 0,
    pointHoverRadius: 4,
  }))
  const theme = chartTheme()
  const options: ChartOptions = baseOptions({
    scales: {
      r: {
        ...rangeOf(input, false),
        ticks: { color: theme.text, backdropColor: 'transparent', ...moneyTicks(columns.values) },
        grid: { color: theme.grid },
        angleLines: { color: theme.grid },
        pointLabels: { color: theme.text },
      },
    },
    plugins: pluginsOf(input, gridCallbacks(grid, fmt, null)),
  } as ChartOptions)
  return { type: 'radar', data: chartData(grid.labels, datasets), options, description: describe(kindLabel(input.kind), columns, columnHeader), notes: [] }
}
