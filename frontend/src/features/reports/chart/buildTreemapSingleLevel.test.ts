import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportChartInput } from '../../../shared/model/reportTypes'
import { buildChart } from './buildChart'

/**
 * 계열 없는 트리맵(한 단계)의 사각형은 l=0인 잎이다. 라벨 formatter가 `[상위 이름, 값]`을 돌려줘야 한다.
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

describe('buildChart: 한 단계 트리맵의 라벨', () => {
  // 테스트 코드: RC-094
  it('계열 없는 트리맵의 잎 사각형은 상위 이름과 값을 라벨로 단다', () => {
    // given: 계열 없는 트리맵 결과와 잎 사각형
    const result = resultOf({ columns: [VENDOR, { ...AMOUNT, index: 1 }], rows: [['Silverfort', 4_000_000], ['Okta', 2_000_000]] })
    const format = formatter(base, result)
    const tile: Tile = { g: 'Silverfort', l: 0, v: 4_000_000, isLeaf: true, _data: { upper: 'Silverfort', path: 'Silverfort', children: [{ upper: 'Silverfort', value: 4_000_000 }] } }

    // when: 라벨 글자를 구한다
    const label = format({ raw: tile })

    // then: [상위 이름, 값] 배열이고 값에 4,000,000이 들어 있다
    expect(Array.isArray(label)).toBe(true)
    expect(label[0]).toBe('Silverfort')
    expect(String(label[1])).toContain('4,000,000')
  })

  // 테스트 코드: RC-094
  it('두 단계 트리맵은 상위 라벨이 비고 잎 라벨이 하위 이름이다', () => {
    // given: 계열 있는 트리맵 결과와 상위·잎 사각형
    const result = resultOf({
      columns: [VENDOR, STATUS, AMOUNT],
      rows: [['Silverfort', 'Won', 3_000_000], ['Okta', 'Open', 2_000_000]],
    })
    const format = formatter({ ...base, series: 1, values: [2] }, result)
    const parent: Tile = { g: 'Silverfort', l: 0, v: 3_000_000, _data: { upper: 'Silverfort', children: [] } }
    const leaf: Tile = { g: 'Won', l: 1, v: 3_000_000, _data: { lower: 'Won', children: [{ upper: 'Silverfort', lower: 'Won', value: 3_000_000 }] } }

    // when: 상위 타일과 잎 타일의 레이블을 만든다
    const actual = format({ raw: parent })
    const actual2 = format({ raw: leaf })
    // then: 상위 사각형 라벨은 빈 글자이고 잎 라벨은 [하위 이름, 값]이다
    expect(actual).toBe('')
    expect(actual2).toEqual(['Won', expect.stringContaining('3,000,000')])
  })
})
