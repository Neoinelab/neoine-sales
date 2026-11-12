import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportChartInput } from '../../../shared/model/reportTypes'
import { buildChart } from './buildChart'

/**
 * 트리맵 데이터가 실제 플러그인(chartjs-chart-treemap 4.2.2)을 거친 뒤에도
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

describe('buildChart: 트리맵의 플러그인 연동', () => {
  // 테스트 코드: RC-095
  it('트리 행의 키는 플러그인 예약 이름과 겹치지 않고 모든 행에 값 키가 있다', () => {
    // when: 두 단계 트리맵을 만든다
    const { dataset } = built()
    const keys = new Set([...dataset.groups, ...dataset.tree.flatMap((row) => Object.keys(row))])

    // then: 예약 이름이 하나도 없고 모든 행의 값이 숫자다
    expect(['group', 'groupIndex', 'label', 'path', 'children', '_idx', '_leaf'].filter((name) => keys.has(name))).toEqual([])
    expect(dataset.tree.every((row) => typeof row[dataset.key] === 'number')).toBe(true)
  })

  // 테스트 코드: RC-094
  it('큰 사각형은 자기 상위 이름으로 색을 정한다', () => {
    // given: 두 단계 트리맵
    const { dataset } = built()
    // when: 상위 사각형 둘의 색을 구한다
    const silverfort = dataset.backgroundColor({ raw: parentTile(dataset.groups, 'Silverfort', 4_000_000) })
    const okta = dataset.backgroundColor({ raw: parentTile(dataset.groups, 'Okta', 2_000_000) })

    // then: 두 색이 서로 다르다
    expect(silverfort).not.toBe(okta)
  })

  // 테스트 코드: RC-094
  it('하위 사각형은 부모와 같은 색이고 다른 부모와는 다르다', () => {
    // given: 두 단계 트리맵
    const { dataset } = built()
    const color = (tile: Tile): string => dataset.backgroundColor({ raw: tile })
    // when: 부모와 하위 사각형의 색을 구한다
    const parentA = color(parentTile(dataset.groups, 'Silverfort', 4_000_000))

    // then: 같은 부모의 하위는 부모 색이고 다른 부모의 하위는 다르다
    expect(color(leafTile(dataset.groups, 'Silverfort', 'Won', 3_000_000))).toBe(parentA)
    expect(color(leafTile(dataset.groups, 'Silverfort', 'Open', 1_000_000))).toBe(parentA)
    expect(color(leafTile(dataset.groups, 'Okta', 'Open', 2_000_000))).not.toBe(parentA)
  })

  // 테스트 코드: RC-094
  it('상위 사각형의 툴팁 제목은 상위 이름이다', () => {
    // given: 두 단계 트리맵
    const { dataset, callbacks } = built()

    // when: 상위 사각형의 툴팁 제목을 구한다
    const actual = callbacks.title([{ raw: parentTile(dataset.groups, 'Silverfort', 4_000_000) }])

    // then: Silverfort다
    expect(actual).toBe('Silverfort')
  })

  // 테스트 코드: RC-094
  it('하위 사각형의 툴팁 제목은 상위 이름이고 본문은 하위 이름이다', () => {
    // given: 두 단계 트리맵과 하위 사각형
    const { dataset, callbacks } = built()
    const tile = leafTile(dataset.groups, 'Okta', 'Open', 2_000_000)

    // when: 타일에 대한 툴팁 제목과 본문을 만든다
    const actual = callbacks.title([{ raw: tile }])
    const actual2 = callbacks.label({ raw: tile })
    // then: 툴팁 제목은 상위 이름 Okta이고 본문에 하위 이름 Open이 들어 있다
    expect(actual).toBe('Okta')
    expect(actual2).toContain('Open')
  })

  // 테스트 코드: RC-094
  it('라벨은 하위 사각형에만 하위 이름으로 단다', () => {
    // given: 두 단계 트리맵
    const { dataset } = built()

    // when: 상위 타일과 잎 타일의 레이블을 만든다
    const actual = dataset.labels.formatter({ raw: parentTile(dataset.groups, 'Silverfort', 4_000_000) })
    const actual2 = dataset.labels.formatter({ raw: leafTile(dataset.groups, 'Silverfort', 'Won', 3_000_000) })
    // then: 상위 사각형 라벨은 빈 글자이고 하위 사각형 라벨에는 하위 이름이 있다
    expect(actual).toBe('')
    expect(actual2).toContain('Won')
  })
})
