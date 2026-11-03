import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../../test/reportDesigner'
import type { ReportChartInput } from '../../../../shared/model/reportTypes'
import { buildChart } from '../buildChart'

/**
 * 리뷰 후속(Minor): 선버스트 범례 항목은 안쪽(상위) 이름이다. Chart.js 기본 클릭은 `toggleDataVisibility(index)`로 모든 데이터셋의
 * 같은 index를 숨기므로, 바깥 고리에서는 관련 없는 하위 조각이 숨고 고리가 어긋난다.
 * 계약: 범례 클릭 뒤에는 (a) 아무것도 숨지 않거나(클릭 무시, `legend.onClick`이 null·false·함수) (b) 그 상위 조각과
 * 그 상위의 모든 하위 조각만 함께 숨는다. 기본 동작(`onClick` 미지정)은 안 된다.
 * 숨김 판정은 Chart.js처럼 `toggleDataVisibility`(모든 데이터셋의 같은 index)와 조각의 `meta.data[i].hidden`을 모두 센다.
 */

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }
const VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
const STATUS = resultColumn({ index: 1, field: 'deal.status', label: 'Status', type: 'code', valueType: 'text', format: null, group: true })
const AMOUNT = resultColumn({ index: 2, field: 'deal.amount', label: '금액 합계', type: 'number', valueType: 'integer', format: null, unit: 'krw', aggregate: 'sum' })
// 상위 Silverfort(하위 Won·Open·Lost 3개), Okta(하위 Open 1개), Ping(하위 Won 1개)
const RESULT = resultOf({
  columns: [VENDOR, STATUS, AMOUNT],
  rows: [
    ['Silverfort', 'Won', 3],
    ['Silverfort', 'Open', 2],
    ['Silverfort', 'Lost', 1],
    ['Okta', 'Open', 4],
    ['Ping', 'Won', 5],
  ],
})

const input: ReportChartInput = {
  kind: 'sunburst',
  category: 0,
  series: 1,
  values: [2],
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

type OnClick = ((event: unknown, item: { index: number; text: string }, legend: { chart: unknown }) => void) | null | false | undefined

function clickLegend(parentIndex: number) {
  const built = buildChart(input, RESULT, CTX) as unknown as {
    data: { labels: string[]; datasets: { data: unknown[] }[] }
    options: { plugins: { legend: { onClick?: OnClick } } }
  }
  const sizes = built.data.datasets.map((d) => d.data.length)
  const hiddenIndices = new Set<number>()
  const meta = sizes.map((n) => Array.from({ length: n }, () => ({ hidden: false })))
  const chart = {
    data: built.data,
    toggleDataVisibility: (i: number) => (hiddenIndices.has(i) ? hiddenIndices.delete(i) : hiddenIndices.add(i)),
    getDataVisibility: (i: number) => !hiddenIndices.has(i),
    getDatasetMeta: (d: number) => ({ data: meta[d] }),
    isDatasetVisible: () => true,
    setDatasetVisibility: () => undefined,
    update: () => undefined,
    draw: () => undefined,
    render: () => undefined,
  }
  const onClick = built.options.plugins.legend.onClick
  if (typeof onClick === 'function') onClick.call(chart, {}, { index: parentIndex, text: built.data.labels[parentIndex] ?? '' }, { chart })
  const hidden = (ring: number): number[] =>
    Array.from({ length: sizes[ring] ?? 0 }, (_, i) => i).filter((i) => hiddenIndices.has(i) || meta[ring]?.[i]?.hidden)
  return { onClick, labels: built.data.labels, hiddenInner: hidden(0), hiddenOuter: hidden(1) }
}

describe('buildChart: 선버스트 범례 클릭 (리뷰 후속 Minor)', () => {
  it('does not leave the default legend click that toggles the same index in both rings', () => {
    expect(clickLegend(0).onClick).not.toBeUndefined()
  })

  it('hides no ring piece or exactly the clicked parent and all of its children (Silverfort has 3 children)', () => {
    const { hiddenInner, hiddenOuter } = clickLegend(0)

    const ignored = hiddenInner.length === 0 && hiddenOuter.length === 0
    const together = hiddenInner.join() === '0' && hiddenOuter.join() === '0,1,2'
    expect(ignored || together).toBe(true)
  })

  it('does not hide an unrelated child when a later parent is clicked (Okta is the second parent with one child)', () => {
    const { hiddenInner, hiddenOuter } = clickLegend(1)

    const ignored = hiddenInner.length === 0 && hiddenOuter.length === 0
    const together = hiddenInner.join() === '1' && hiddenOuter.join() === '3'
    expect(ignored || together).toBe(true)
  })
})
