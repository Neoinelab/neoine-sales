import type { ChartOptions } from 'chart.js'
import { chartTheme } from '../../../../shared/ui/chartTheme'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { treemapTree } from '../compute/treemapTree'
import { pivot } from '../pivot'
import { baseOptions, chartData, color, describe, pluginsOf, showValue, tooMany, withAlpha, type BuildInput, type BuildOutcome } from './common'

/**
 * 플러그인이 사각형마다 넘겨 주는 값(필요한 것만). `l`은 단계(0 = 상위, 1 = 잎).
 * 상위 사각형의 `_data`는 `{ [상위 키]: 이름, path, children(입력 행들) }`, 잎의 `_data`는 `{ [하위 키]: 이름, path: '상위.하위', children: [입력 행] }`다.
 * 입력 행 키는 플러그인 예약 이름과 겹치지 않는 `upper`·`lower`(`treemapTree`)라 상위 이름은 `children[0].upper`로 구한다.
 */
interface Tile {
  g?: string
  l?: number
  v: number
  _data?: { upper?: string; lower?: string; children?: { upper?: string; lower?: string }[] }
}
const parentOf = (tile: Tile): string | undefined => (tile.l === 0 ? (tile._data?.upper ?? tile.g) : (tile._data?.children?.[0]?.upper ?? tile._data?.upper ?? tile.g))
interface TileContext {
  raw: Tile
}

/** 트리맵: 그룹핑 1~2개, 값 1개. 범주 = 상위 수준(큰 사각형), 계열 = 하위 수준(그 안의 사각형). */
export function buildTreemap({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const grid = pivot(input, result, columns, fmt)
  const columnsHasSeries = columns.series !== null
  const limit = tooMany(grid.labels.length * grid.sets.length)
  if (limit) return limit
  const { tree, groups, skipped } = treemapTree(grid, columnsHasSeries)
  const unit = columns.values[0]
  const oneLevel = groups.length === 1
  const groupNames = [...new Set(tree.map((row) => row.upper))]
  const tint = (tile: Tile): string => {
    const group = parentOf(tile)
    const at = group === undefined ? 0 : Math.max(0, groupNames.indexOf(group))
    return withAlpha(color(at), 0xd9)
  }
  const text = (value: number): string => (unit ? showValue(value, unit, fmt) : String(value))
  const theme = chartTheme()
  const dataset = {
    label: unit ? columnHeader(unit) : '',
    tree,
    key: 'value',
    groups,
    spacing: 1,
    borderWidth: 1,
    borderColor: theme.grid,
    backgroundColor: (c: TileContext) => tint(c.raw),
    captions: { display: true, color: '#111827', font: { weight: 'bold' } },
    labels: {
      display: true,
      color: '#111827',
      formatter: (c: TileContext) => {
        // 한 단계(계열 없음)면 사각형이 상위의 잎이라 상위 이름을 쓴다.
        const sub = c.raw.l === 0 && !oneLevel ? undefined : oneLevel ? parentOf(c.raw) : (c.raw._data?.children?.[0]?.lower ?? c.raw.g)
        return typeof sub === 'string' ? [sub, text(c.raw.v)] : ''
      },
    },
  }
  const cb = {
    tooltipTitle: (items: readonly TileContext[]): string => (items[0] ? parentOf(items[0].raw) : undefined) ?? '',
    tooltipLabel: (c: TileContext): string => {
      const sub = c.raw.l === 0 ? undefined : (c.raw._data?.children?.[0]?.lower ?? c.raw.g)
      return `${typeof sub === 'string' ? sub : (c.raw.g ?? '')}: ${text(c.raw.v)}`
    },
  }
  const plugins = pluginsOf(input, cb, false)
  // 트리맵은 플러그인이 자기 글자를 그린다. 데이터 레이블 플러그인은 끈다.
  const options: ChartOptions = baseOptions({ plugins: { ...plugins, datalabels: { display: false } } as ChartOptions['plugins'] })
  const notes = skipped > 0 ? [`값이 0 이하이거나 빈 칸 ${skipped}개는 그리지 않았습니다`] : []
  return { type: 'treemap', data: chartData([], [dataset]), options, description: describe(kindLabel(input.kind), columns, columnHeader), notes }
}
