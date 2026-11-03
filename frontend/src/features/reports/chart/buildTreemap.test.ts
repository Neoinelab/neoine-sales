import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportChartInput } from '../../../shared/model/reportTypes'
import { buildChart } from './buildChart'

/**
 * 리뷰 후속(Major 1): 트리맵 데이터가 실제 플러그인(chartjs-chart-treemap 4.2.2)을 거친 뒤에도
 * 상위 노드 이름이 살아 있어야 한다. 전역 mock 때문에 플러그인의 `buildData`를 직접 돌릴 수 없어(내보내지 않는 내부 함수),
 * 플러그인이 만드는 사각형 모양을 이 파일이 `dataset.groups`로 재현해 색·라벨·툴팁 콜백에 넣는다.
 * 플러그인 동작(esm 341~391행): 묶음 노드는 `_data = { [그룹 키]: 이름, group: 그룹 키 이름, groupIndex, label: 이름, path, children }`이고
 * 사각형은 `{ g: 이름, l: 단계, v: 합, _data }`다. 잎의 `children`은 입력 행들이다.
 */

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }
const VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
const STATUS = resultColumn({ index: 1, field: 'deal.status', label: 'Status', type: 'code', valueType: 'text', format: null, group: true })
const AMOUNT = resultColumn({ index: 2, field: 'deal.amount', label: '금액 합계', type: 'number', valueType: 'integer', format: null, unit: 'krw', aggregate: 'sum' })
const RESULT = resultOf({
  columns: [VENDOR, STATUS, AMOUNT],
  rows: [
    ['Silverfort', 'Won', 3_000_000],
    ['Silverfort', 'Open', 1_000_000],
    ['Okta', 'Open', 2_000_000],
  ],
})

const input: ReportChartInput = {
  kind: 'treemap',
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

interface Tile {
  g: string
  l: number
  v: number
  _data: Record<string, unknown>
}
interface TreemapDataset {
  groups: [string, string]
  key: string
  tree: Record<string, unknown>[]
  backgroundColor: (c: { raw: Tile }) => string
  labels: { formatter: (c: { raw: Tile }) => string | string[] }
}
interface Callbacks {
  title: (items: { raw: Tile }[]) => string
  label: (c: { raw: Tile }) => string
}

function built() {
  const out = buildChart(input, RESULT, CTX) as unknown as { data: { datasets: unknown[] }; options: { plugins: { tooltip: { callbacks: Callbacks } } } }
  return { dataset: out.data.datasets[0] as TreemapDataset, callbacks: out.options.plugins.tooltip.callbacks }
}

/** 플러그인이 만들어 주는 상위 사각형 */
function parentTile(groups: [string, string], name: string, v: number): Tile {
  return { g: name, l: 0, v, _data: { [groups[0]]: name, group: groups[0], groupIndex: 0, label: name, path: name, children: [] } }
}
/** 플러그인이 만들어 주는 하위(잎) 사각형: `children`은 입력 행이다. */
function leafTile(groups: [string, string], parent: string, name: string, v: number): Tile {
  const row = { [groups[0]]: parent, [groups[1]]: name, value: v }
  return { g: name, l: 1, v, _data: { [groups[1]]: name, group: groups[1], groupIndex: 1, label: name, path: `${parent}.${name}`, children: [row] } }
}

describe('buildChart: 트리맵의 플러그인 연동 (리뷰 후속 Major 1)', () => {
  it('keeps the tree row keys apart from the plugin reserved properties and keeps the value key in every row', () => {
    const { dataset } = built()
    const keys = new Set([...dataset.groups, ...dataset.tree.flatMap((row) => Object.keys(row))])

    expect(['group', 'groupIndex', 'label', 'path', 'children', '_idx', '_leaf'].filter((name) => keys.has(name))).toEqual([])
    expect(dataset.tree.every((row) => typeof row[dataset.key] === 'number')).toBe(true)
  })

  it('colors the big rectangles by their own parent name', () => {
    const { dataset } = built()
    const silverfort = dataset.backgroundColor({ raw: parentTile(dataset.groups, 'Silverfort', 4_000_000) })
    const okta = dataset.backgroundColor({ raw: parentTile(dataset.groups, 'Okta', 2_000_000) })

    expect(silverfort).not.toBe(okta)
  })

  it('colors a child rectangle like its parent and apart from the other parent', () => {
    const { dataset } = built()
    const color = (tile: Tile): string => dataset.backgroundColor({ raw: tile })
    const parentA = color(parentTile(dataset.groups, 'Silverfort', 4_000_000))

    expect(color(leafTile(dataset.groups, 'Silverfort', 'Won', 3_000_000))).toBe(parentA)
    expect(color(leafTile(dataset.groups, 'Silverfort', 'Open', 1_000_000))).toBe(parentA)
    expect(color(leafTile(dataset.groups, 'Okta', 'Open', 2_000_000))).not.toBe(parentA)
  })

  it('titles the tooltip of a parent rectangle with the parent name', () => {
    const { dataset, callbacks } = built()

    expect(callbacks.title([{ raw: parentTile(dataset.groups, 'Silverfort', 4_000_000) }])).toBe('Silverfort')
  })

  it('titles the tooltip of a child rectangle with its parent name and labels it with the child name', () => {
    const { dataset, callbacks } = built()
    const tile = leafTile(dataset.groups, 'Okta', 'Open', 2_000_000)

    expect(callbacks.title([{ raw: tile }])).toBe('Okta')
    expect(callbacks.label({ raw: tile })).toContain('Open')
  })

  it('captions only child rectangles with the child name through the label formatter', () => {
    const { dataset } = built()

    expect(dataset.labels.formatter({ raw: parentTile(dataset.groups, 'Silverfort', 4_000_000) })).toBe('')
    expect(dataset.labels.formatter({ raw: leafTile(dataset.groups, 'Silverfort', 'Won', 3_000_000) })).toContain('Won')
  })
})
