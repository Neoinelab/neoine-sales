import type { ChartOptions } from 'chart.js'
import { columnHeader } from '../../designer/format/formatCell'
import { kindLabel } from '../chartKinds'
import { pivot } from '../pivot'
import { sunburstRings } from '../compute/sunburstRings'
import { baseOptions, chartData, color, describe, gridCallbacks, pluginsOf, showValue, tooMany, withAlpha, type BuildInput, type BuildOutcome } from './common'

/** 원형·도넛형: 데이터셋 하나, 범주마다 한 조각. */
export function buildPie({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const grid = pivot(input, result, columns, fmt)
  const limit = tooMany(grid.labels.length * grid.sets.length)
  if (limit) return limit
  const set = grid.sets[0]
  const dataset = { label: set?.label ?? '', data: grid.labels.map((_, i) => set?.cells[i]?.value ?? 0), backgroundColor: grid.labels.map((_, i) => color(i)) }
  return {
    type: input.kind === 'pie' ? 'pie' : 'doughnut',
    data: chartData(grid.labels, [dataset]),
    options: baseOptions({ plugins: pluginsOf(input, gridCallbacks(grid, fmt, null, true)) }),
    description: describe(kindLabel(input.kind), columns, columnHeader),
    notes: [],
  }
}

// 도넛은 데이터셋 0이 가장 바깥 고리이고 뒤 데이터셋일수록 안쪽에 그려진다(Chart.js 고리 순서).
// 선버스트는 데이터셋 0 = 안쪽(상위)이어야 하므로 고리마다 반지름·구멍 비율을 직접 정한다.
// 고리 두께 = 반지름 × (1 − 구멍) / 2(데이터셋 가중치 합 2). 안쪽 고리는 [0.29, 0.58], 바깥 고리는 [0.60, 1.00](최대 반지름 비율).
const INNER = { radius: '58%', cutout: '0%' }
const OUTER = { radius: '140%', cutout: '42.857%' }

// 범례 항목은 안쪽(상위) 이름인데 기본 클릭은 두 고리의 같은 index를 숨겨 고리가 어긋난다. 클릭을 끈다.
function withLegendClick(plugins: ChartOptions['plugins']): ChartOptions['plugins'] {
  return { ...plugins, legend: { ...plugins?.legend, onClick: () => undefined } }
}

/** 선버스트: 겹친 두 도넛. 안쪽 = 상위(범주) 합계, 바깥 = 하위(계열) 항목이 상위 조각 각도 안에 놓인다. */
export function buildSunburst({ input, result, columns, fmt }: BuildInput): BuildOutcome {
  const grid = pivot(input, result, columns, fmt)
  const limit = tooMany(grid.labels.length * grid.sets.length)
  if (limit) return limit
  const rings = sunburstRings(grid)
  const unit = columns.values[0]
  // 바깥 고리 색은 상위 조각의 순번으로 정한다(앞 N자로 잘린 표시 이름이 같은 상위끼리 섞이지 않게).
  const seen = new Map<number, number>()
  const outerColors = rings.outer.map((_, k) => {
    const parent = rings.outerParent[k] ?? 0
    const nth = seen.get(parent) ?? 0
    seen.set(parent, nth + 1)
    return withAlpha(color(parent), Math.max(0x66, 0xe6 - nth * 0x22))
  })
  const innerRing = { label: '상위', data: rings.inner.map((p) => p.value), backgroundColor: rings.inner.map((_, i) => color(i)), weight: 1 }
  // 계열이 없으면 고리는 상위 하나뿐이다(값 열 머리글 이름의 하위 조각을 만들지 않는다).
  const datasets =
    columns.series === null
      ? [innerRing]
      : [
          { ...innerRing, ...INNER },
          { label: '하위', data: rings.outer.map((o) => o.value), backgroundColor: outerColors, weight: 1, ...OUTER },
        ]
  const text = (datasetIndex: number, dataIndex: number): string => {
    const value = datasetIndex === 0 ? rings.inner[dataIndex]?.value : rings.outer[dataIndex]?.value
    return unit && value !== undefined ? showValue(value, unit, fmt) : '—'
  }
  const cb = {
    tooltipLabel: (c: { datasetIndex: number; dataIndex: number }): string => {
      const name = c.datasetIndex === 0 ? rings.inner[c.dataIndex]?.label : `${rings.outer[c.dataIndex]?.parent} / ${rings.outer[c.dataIndex]?.label}`
      return `${name ?? ''}: ${text(c.datasetIndex, c.dataIndex)}`
    },
    tooltipTitle: (): string => '',
    dataLabel: (_value: unknown, c: { datasetIndex: number; dataIndex: number }): string => text(c.datasetIndex, c.dataIndex),
  }
  const notes = rings.skipped > 0 ? [`값이 0 이하이거나 빈 칸 ${rings.skipped}개는 그리지 않았습니다`] : []
  return {
    type: 'doughnut',
    data: chartData(rings.inner.map((p) => p.label), datasets),
    options: baseOptions({ plugins: withLegendClick(pluginsOf(input, cb)) }),
    description: describe(kindLabel(input.kind), columns, columnHeader),
    notes,
  }
}
