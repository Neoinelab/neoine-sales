import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportChartInput } from '../../../shared/model/reportTypes'
import { buildChart } from './buildChart'

/**
 * 재리뷰 후속 AC10: 계열 없는 트리맵(한 단계)의 사각형은 l=0인 잎이다. 라벨 formatter가 `[상위 이름, 값]`을 돌려줘야 한다.
 * 두 단계(계열 있음)의 동작(상위 사각형은 빈 문자열, 잎은 하위 이름)은 그대로다.
 */
const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }
const VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
const STATUS = resultColumn({ index: 1, field: 'deal.status', label: 'Status', type: 'code', valueType: 'text', format: null, group: true })
const AMOUNT = resultColumn({ index: 2, field: 'deal.amount', label: '금액 합계', type: 'number', valueType: 'integer', format: null, unit: 'krw', aggregate: 'sum' })

const base: ReportChartInput = {
  kind: 'treemap',
  category: 0,
  series: null,
  values: [1],
  swap: false,
  title: '',
  legend: 'top',
  dataLabels: false,
  categoryAxisTitle: '',
  valueAxisTitle: '',
  valueMin: null,
  valueMax: null,
  secondaryAxis: false,
  histogram: null,
  showTotal: false,
  comboSeries: null,
}

interface Tile {
  g: string
  l: number
  v: number
  isLeaf?: boolean
  _data: Record<string, unknown>
}
interface Dataset {
  labels: { formatter: (c: { raw: Tile }) => string | string[] }
}

function formatter(input: ReportChartInput, result: ReturnType<typeof resultOf>) {
  const out = buildChart(input, result, CTX) as unknown as { data: { datasets: unknown[] } }
  return (out.data.datasets[0] as Dataset).labels.formatter
}

describe('buildChart: 한 단계 트리맵의 라벨 (재리뷰 후속 AC10)', () => {
  it('captions a leaf rectangle of the one-level treemap with the parent name and the value', () => {
    const result = resultOf({ columns: [VENDOR, { ...AMOUNT, index: 1 }], rows: [['Silverfort', 4_000_000], ['Okta', 2_000_000]] })
    const format = formatter(base, result)
    const tile: Tile = { g: 'Silverfort', l: 0, v: 4_000_000, isLeaf: true, _data: { upper: 'Silverfort', path: 'Silverfort', children: [{ upper: 'Silverfort', value: 4_000_000 }] } }

    const label = format({ raw: tile })

    expect(Array.isArray(label)).toBe(true)
    expect(label[0]).toBe('Silverfort')
    expect(String(label[1])).toContain('4,000,000')
  })

  it('keeps the two-level behavior: empty caption for the parent and the child name for a leaf', () => {
    const result = resultOf({
      columns: [VENDOR, STATUS, AMOUNT],
      rows: [['Silverfort', 'Won', 3_000_000], ['Okta', 'Open', 2_000_000]],
    })
    const format = formatter({ ...base, series: 1, values: [2] }, result)
    const parent: Tile = { g: 'Silverfort', l: 0, v: 3_000_000, _data: { upper: 'Silverfort', children: [] } }
    const leaf: Tile = { g: 'Won', l: 1, v: 3_000_000, _data: { lower: 'Won', children: [{ upper: 'Silverfort', lower: 'Won', value: 3_000_000 }] } }

    expect(format({ raw: parent })).toBe('')
    expect(format({ raw: leaf })).toEqual(['Won', expect.stringContaining('3,000,000')])
  })
})
