import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportCell, ReportChartInput, ReportChartKind, ReportResult } from '../../../shared/model/reportTypes'
import { columnHeader, formatCell } from '../designer/format/formatCell'
import { buildChart } from './buildChart'

/**
 * `buildChart(input, result, ctx)`: 차트 설정(컬럼은 결과 열 index) + 조회 결과 → Chart.js에 넘길 값.
 * 반환: `{ type, data: { labels, datasets }, options } | { problem: string }`.
 * 계약(테스트가 정한 부분): 범주 이름은 data.labels(분산형도 점 이름으로 같은 자리), 툴팁은 options.plugins.tooltip.callbacks.label(context),
 * 데이터 레이블은 options.plugins.datalabels.formatter(value, { dataIndex, datasetIndex, dataset }).
 */

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }
const COLORS = ['#94a3b8', '#60a5fa', '#34d399', '#fbbf24', '#f472b6']

const VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
const STATUS = resultColumn({ index: 1, field: 'deal.status', label: 'Status', type: 'code', valueType: 'text', format: null, group: true })
const amount = (index: number, aggregate: 'sum' | 'avg' | 'count' = 'sum') =>
  resultColumn({ index, field: 'deal.amount', label: '금액 합계', type: 'number', valueType: 'integer', format: null, unit: 'krw', aggregate })
const users = (index: number) =>
  resultColumn({ index, field: 'deal.users', label: 'Users count', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum' })

/** 그룹 1개 + 금액 + Users count. 마지막 Vendor는 값이 없다. */
const ONE: ReportResult = resultOf({
  columns: [VENDOR, amount(1), users(2)],
  rows: [
    ['Silverfort', 3_000_000, 30],
    ['Okta', 1_500_000, 10],
    [null, 500_000, 5],
  ],
})

/** 그룹 2개(Vendor, Status) + 금액. Okta에는 Won 조합이 없다. */
const TWO: ReportResult = resultOf({
  columns: [VENDOR, STATUS, amount(2)],
  rows: [
    ['Silverfort', 'Won', 3_000_000],
    ['Silverfort', 'Open', 1_000_000],
    ['Okta', 'Open', 2_000_000],
  ],
})

function chart(over: Partial<ReportChartInput> = {}): ReportChartInput {
  return {
    kind: 'bar',
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
    ...over,
  }
}

/** 콤보 계열 설정: 첫째 막대, 나머지 꺾은선(`secondary`이면 꺾은선을 보조 축에). 서버가 채워 주는 옛 규칙과 같다. */
const comboOf = (count: number, secondary = false) => [
  { type: 'column' as const, secondary: false },
  ...Array.from({ length: count - 1 }, () => ({ type: 'line' as const, secondary })),
]

/** 읽기 전용 경로 접근(any 없이 중첩 옵션을 읽는다). */
function get(root: unknown, ...path: (string | number)[]): unknown {
  let current: unknown = root
  for (const key of path) {
    if (typeof current !== 'object' || current === null) return undefined
    current = (current as Record<string | number, unknown>)[key]
  }
  return current
}

interface Built {
  type: string
  data: { labels: string[]; datasets: Record<string, unknown>[] }
  options: Record<string, unknown>
}

function build(input: ReportChartInput, result: ReportResult): Built {
  const built = buildChart(input, result, CTX) as unknown as Built | { problem: string }
  if ('problem' in built) throw new Error(`차트를 만들 수 없음: ${built.problem}`)
  return built
}

const problemOf = (input: ReportChartInput, result: ReportResult): string | null => {
  const built = buildChart(input, result, CTX) as unknown as { problem?: string }
  return built.problem ?? null
}

const dataOf = (b: Built, i = 0): unknown[] => (b.data.datasets[i]?.data as unknown[]) ?? []

describe('buildChart: 종류별 Chart.js 종류와 옵션', () => {
  // 테스트 코드: RC-087
  it('막대는 세로 막대 차트로, 누적 없이 그린다', () => {
    // when: 묶은 세로 막대를 만든다
    const b = build(chart({ kind: 'bar' }), ONE)

    // then: 종류는 bar이고 가로 방향·누적이 아니다
    expect(b.type).toBe('bar')
    expect(get(b.options, 'indexAxis')).not.toBe('y')
    expect(get(b.options, 'scales', 'x', 'stacked')).toBeFalsy()
  })

  // 테스트 코드: RC-087
  it('가로 막대는 범주 축이 y다', () => {
    // when: 묶은 가로 막대를 만든다
    const b = build(chart({ kind: 'horizontal_bar' }), ONE)

    // then: 종류는 bar이고 indexAxis가 y다
    expect(b.type).toBe('bar')
    expect(get(b.options, 'indexAxis')).toBe('y')
  })

  // 테스트 코드: RC-087
  it('누적 막대는 두 축 모두 누적한다', () => {
    // when: 누적 세로 막대를 만든다
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2], category: 0 }), TWO)

    // then: x·y 축이 모두 stacked다
    expect(b.type).toBe('bar')
    expect(get(b.options, 'scales', 'x', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
  })

  // 테스트 코드: RC-088
  it('100% 누적은 두 축을 누적하고 값 축 최대를 100으로 둔다', () => {
    // when: 100% 누적 세로 막대를 만든다
    const b = build(chart({ kind: 'stacked_100_bar', series: 1, values: [2] }), TWO)

    // then: x·y 축이 stacked이고 y 최대가 100이다
    expect(get(b.options, 'scales', 'x', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'max')).toBe(100)
  })

  // 테스트 코드: RC-089
  it('꺾은선은 채우지 않고 영역은 원점부터 채운다', () => {
    // when: 꺾은선과 영역을 만든다
    const line = build(chart({ kind: 'line' }), ONE)
    const area = build(chart({ kind: 'area' }), ONE)

    // then: 꺾은선은 fill false, 영역은 fill origin이다
    expect(line.type).toBe('line')
    expect(line.data.datasets.every((d) => d.fill === false)).toBe(true)
    expect(area.type).toBe('line')
    expect(area.data.datasets.every((d) => d.fill === 'origin')).toBe(true)
  })

  // 테스트 코드: RC-090
  it.each<[ReportChartKind]>([['pie'], ['doughnut']])('원형·도넛형은 데이터셋 하나에 조각마다 색을 주고 축이 없다 (%s)', (kind) => {
    // when: 원형 또는 도넛형을 만든다
    const b = build(chart({ kind }), ONE)

    // then: 종류가 같고 데이터셋 하나, 조각 색 3개이며 scales가 없다
    expect(b.type).toBe(kind)
    expect(b.data.datasets).toHaveLength(1)
    expect(b.data.datasets[0]?.backgroundColor).toEqual(COLORS.slice(0, 3))
    expect(b.options.scales).toBeUndefined()
  })

  // 테스트 코드: RC-091
  it('분산형은 첫 값을 x로 둘째 값을 y로 그리고 범주로 점 이름을 붙인다', () => {
    // when: 분산형을 만든다
    const b = build(chart({ kind: 'scatter', values: [1, 2] }), ONE)

    // then: 점이 {x, y}이고 점 이름이 범주 이름이다
    expect(b.type).toBe('scatter')
    expect(dataOf(b)).toEqual([
      { x: 3_000_000, y: 30 },
      { x: 1_500_000, y: 10 },
      { x: 500_000, y: 5 },
    ])
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
  })

  // 테스트 코드: RC-104
  it('콤보는 첫 값을 막대로 나머지를 꺾은선으로 그린다', () => {
    // when: 계열 설정이 있는 콤보를 만든다
    const b = build(chart({ kind: 'combo', values: [1, 2], comboSeries: comboOf(2) }), ONE)

    // then: 막대 + 꺾은선 데이터셋이고 보조 축이 없다
    expect(b.type).toBe('bar')
    expect(b.data.datasets[0]?.type).toBe('bar')
    expect(b.data.datasets[1]?.type).toBe('line')
    expect(b.data.datasets[1]?.yAxisID).toBeUndefined()
    expect(get(b.options, 'scales', 'y1')).toBeUndefined()
  })

  // 테스트 코드: RC-104
  it('콤보의 보조 축 꺾은선은 오른쪽 보조 축에 둔다', () => {
    // when: 꺾은선이 보조 축인 콤보를 만든다
    const b = build(chart({ kind: 'combo', values: [1, 2], secondaryAxis: true, comboSeries: comboOf(2, true) }), ONE)

    // then: 막대는 기본 축, 꺾은선은 y1(오른쪽, 격자 없음)이다
    expect(b.data.datasets[0]?.yAxisID).not.toBe('y1')
    expect(b.data.datasets[1]?.yAxisID).toBe('y1')
    expect(get(b.options, 'scales', 'y1', 'position')).toBe('right')
    expect(get(b.options, 'scales', 'y1', 'grid', 'drawOnChartArea')).toBe(false)
  })

  // 테스트 코드: RC-085
  it('모든 차트는 크기에 맞춰 그리고 가로세로 비율을 고정하지 않는다', () => {
    // when: 기본 막대를 만든다
    const b = build(chart(), ONE)

    // then: responsive가 true이고 maintainAspectRatio가 false다
    expect(b.options.responsive).toBe(true)
    expect(b.options.maintainAspectRatio).toBe(false)
  })
})

describe('buildChart: 범주·계열·값', () => {
  // 테스트 코드: RC-081
  it('범주는 첫 등장 순이고 값 하나는 데이터셋 하나가 된다', () => {
    // when: 막대를 만든다
    const b = build(chart(), ONE)

    // then: 범주가 첫 등장 순(빈 값은 (없음))이고 데이터셋 하나에 값이 순서대로 있다
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(b.data.datasets).toHaveLength(1)
    expect(dataOf(b)).toEqual([3_000_000, 1_500_000, 500_000])
  })

  // 테스트 코드: RC-081
  it('값 열마다 열 머리글 이름의 데이터셋이 하나씩 생긴다', () => {
    // when: 값 열 2개로 막대를 만든다
    const b = build(chart({ values: [1, 2] }), ONE)

    // then: 데이터셋 이름이 금액 머리글·Users count이고 둘째 데이터셋 값은 [30, 10, 5]다
    expect(b.data.datasets.map((d) => d.label)).toEqual([columnHeader(amount(1)), 'Users count'])
    expect(dataOf(b, 1)).toEqual([30, 10, 5])
  })

  // 테스트 코드: RC-081
  it('계열 열은 계열 값마다 데이터셋이 되고 빈 칸은 막대에서 0이다', () => {
    // when: 계열이 있는 누적 막대를 만든다
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2] }), TWO)

    // then: 범주·데이터셋 이름이 첫 등장 순이고 빈 조합은 0이다
    expect(b.data.labels).toEqual(['Silverfort', 'Okta'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['Won', 'Open'])
    expect(dataOf(b, 0)).toEqual([3_000_000, 0])
    expect(dataOf(b, 1)).toEqual([1_000_000, 2_000_000])
  })

  // 테스트 코드: RC-089
  it('꺾은선·영역은 빈 칸을 null로 둬서 선이 끊긴다', () => {
    // when: 꺾은선과 영역을 계열과 함께 만든다
    const firstSeries = (['line', 'area'] as const).map((kind) => dataOf(build(chart({ kind, series: 1, values: [2] }), TWO), 0))
    // then: 빈 조합이 null이다
    expect(firstSeries).toEqual([
      [3_000_000, null],
      [3_000_000, null],
    ])
  })

  // 테스트 코드: RC-082
  it('행/열 전환은 범주와 데이터셋을 맞바꾼다', () => {
    // when: 행/열 전환을 켠 막대를 만든다
    const b = build(chart({ kind: 'bar', series: 1, values: [2], swap: true }), TWO)

    // then: 범주와 데이터셋 이름이 서로 바뀌고 값 자리도 따라 바뀐다
    expect(b.data.labels).toEqual(['Won', 'Open'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['Silverfort', 'Okta'])
    expect(dataOf(b, 0)).toEqual([3_000_000, 1_000_000])
    expect(dataOf(b, 1)).toEqual([0, 2_000_000])
  })

  // 테스트 코드: RC-081
  it('범주 값이 비면 (없음)으로 이름 붙인다', () => {
    // when: 막대를 만든다
    const actual = build(chart(), ONE).data.labels

    // then: 범주 이름에 (없음)이 있다
    expect(actual).toContain('(없음)')
  })

  // 테스트 코드: RC-081
  it('범주 이름은 결과 표와 같은 서식으로 쓴다', () => {
    // given: 요일 서식의 날짜 범주 결과
    const date = resultColumn({ index: 0, field: 'deal.expected_close', label: 'Expected Close', type: 'date', valueType: 'date', format: 'weekday', group: true })
    const result = resultOf({ columns: [date, amount(1)], rows: [['2026-10-27', 1_000_000]] })

    // when: 막대를 만든다
    const b = build(chart(), result)

    // then: 범주 이름이 표 칸 서식과 같고 요일이 들어 있다
    expect(b.data.labels).toEqual([formatCell('2026-10-27', date, CTX)])
    expect(b.data.labels[0]).toContain('화')
  })
})

describe('buildChart: 100% 누적', () => {
  // 테스트 코드: RC-088
  it('100% 누적은 범주마다 합 대비 비율로 바꾸고 합이 0이면 0이다', () => {
    // given: 빈 범주를 더한 두 계열 결과
    const rows: ReportCell[][] = [...(TWO.rows as ReportCell[][]), ['Empty', 'Won', 0], ['Empty', 'Open', 0]]
    const result = { ...TWO, rows, totalCount: rows.length }

    // when: 100% 누적 막대를 만든다
    const b = build(chart({ kind: 'stacked_100_bar', series: 1, values: [2] }), result)

    // then: 범주별 비율이 75/25, 0/100, 0/0이다
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', 'Empty'])
    expect(dataOf(b, 0)).toEqual([75, 0, 0])
    expect(dataOf(b, 1)).toEqual([25, 100, 0])
  })

  // 테스트 코드: RC-088
  it('100% 누적의 툴팁은 비율과 원래 값을, 데이터 레이블은 비율을 보인다', () => {
    // given: 데이터 레이블을 켠 100% 누적 차트
    const b = build(chart({ kind: 'stacked_100_bar', series: 1, values: [2], dataLabels: true }), TWO)
    const dataset = b.data.datasets[0]
    const tooltip = get(b.options, 'plugins', 'tooltip', 'callbacks', 'label') as (c: unknown) => string
    const formatter = get(b.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    // when: 툴팁과 데이터 레이블 글자를 구한다
    const tip = tooltip({ dataset, datasetIndex: 0, dataIndex: 0, raw: 75, parsed: { x: 0, y: 75 }, label: 'Silverfort' })
    const label = formatter(75, { dataIndex: 0, datasetIndex: 0, dataset })

    // then: 툴팁에 75와 3,000,000이 있고 레이블은 75% 모양이다
    expect(tip).toContain('75')
    expect(tip).toContain('3,000,000')
    expect(label).toMatch(/^75(\.0)?%$/)
  })
})

describe('buildChart: 제목·범례·레이블·축·범위', () => {
  // 테스트 코드: RC-065
  it('제목은 있을 때만 표시한다', () => {
    // when: 제목 있는 차트와 제목 없는 차트의 옵션을 만든다
    const actual = get(build(chart({ title: 'Vendor별 금액' }), ONE).options, 'plugins', 'title')
    const actual2 = get(build(chart({ title: '' }), ONE).options, 'plugins', 'title', 'display')
    // then: 각각 표시 true·false다
    expect(actual).toMatchObject({ display: true, text: 'Vendor별 금액' })
    expect(actual2).toBe(false)
  })

  // 테스트 코드: RC-065
  it.each([
    ['top', true],
    ['right', true],
    ['bottom', true],
    ['none', false],
  ] as const)('범례 위치를 설정대로 반영하고 none이면 숨긴다 (%s)', (legend, display) => {
    // when: 범례 위치를 지정해 만든다
    const legendOptions = get(build(chart({ legend }), ONE).options, 'plugins', 'legend')

    // then: display가 위치에 맞고 숨기지 않으면 position이 같다
    expect(get(legendOptions, 'display')).toBe(display)
    if (display) expect(get(legendOptions, 'position')).toBe(legend)
  })

  // 테스트 코드: RC-085
  it('데이터 레이블은 켜고 끌 수 있고 결과 표와 같은 서식이다', () => {
    // when: 데이터 레이블을 켠 차트와 끈 차트를 만든다
    const on = build(chart({ dataLabels: true }), ONE)
    const off = build(chart({ dataLabels: false }), ONE)
    const formatter = get(on.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    // then: 켜면 display true와 표 서식 글자, 끄면 false다
    expect(get(on.options, 'plugins', 'datalabels', 'display')).toBe(true)
    expect(get(off.options, 'plugins', 'datalabels', 'display')).toBe(false)
    expect(formatter(3_000_000, { dataIndex: 0, datasetIndex: 0, dataset: on.data.datasets[0] })).toBe('3,000,000')
  })

  // 테스트 코드: RC-065
  it('세로 차트는 가로축에 범주 제목을, 세로축에 값 제목을 달고 비면 달지 않는다', () => {
    // when: 축 제목을 준 차트와 주지 않은 차트를 만든다
    const titled = build(chart({ categoryAxisTitle: 'Vendor', valueAxisTitle: '금액 (원)' }), ONE)
    const blank = build(chart(), ONE)

    // then: x는 범주 제목, y는 값 제목이고 비면 표시하지 않는다
    expect(get(titled.options, 'scales', 'x', 'title')).toMatchObject({ display: true, text: 'Vendor' })
    expect(get(titled.options, 'scales', 'y', 'title')).toMatchObject({ display: true, text: '금액 (원)' })
    expect(get(blank.options, 'scales', 'x', 'title', 'display')).toBeFalsy()
    expect(get(blank.options, 'scales', 'y', 'title', 'display')).toBeFalsy()
  })

  // 테스트 코드: RC-087
  it('가로 막대는 축 제목과 범위가 서로 바뀐다', () => {
    // when: 축 제목·범위를 준 가로 막대를 만든다
    const b = build(chart({ kind: 'horizontal_bar', categoryAxisTitle: 'Vendor', valueAxisTitle: '금액', valueMin: 0, valueMax: 5000 }), ONE)

    // then: y가 범주 제목, x가 값 제목·최소·최대다
    expect(get(b.options, 'scales', 'y', 'title', 'text')).toBe('Vendor')
    expect(get(b.options, 'scales', 'x', 'title', 'text')).toBe('금액')
    expect(get(b.options, 'scales', 'x', 'min')).toBe(0)
    expect(get(b.options, 'scales', 'x', 'max')).toBe(5000)
  })

  // 테스트 코드: RC-065
  it('값 축 최소·최대는 설정이 있을 때만 넣는다', () => {
    // when: 범위를 준 차트와 주지 않은 차트를 만든다
    const ranged = build(chart({ valueMin: 0, valueMax: 5000 }), ONE)
    const auto = build(chart(), ONE)

    // then: 범위가 있으면 min·max가 같고 없으면 키가 없다
    expect(get(ranged.options, 'scales', 'y', 'min')).toBe(0)
    expect(get(ranged.options, 'scales', 'y', 'max')).toBe(5000)
    expect('min' in (get(auto.options, 'scales', 'y') as object)).toBe(false)
    expect('max' in (get(auto.options, 'scales', 'y') as object)).toBe(false)
  })

  // 테스트 코드: RC-065
  it('분산형은 첫 값을 x, 둘째 값을 y 축 제목으로 쓰고 y에 범위를 준다', () => {
    // when: 축 제목과 최소값을 준 분산형을 만든다
    const b = build(chart({ kind: 'scatter', values: [1, 2], categoryAxisTitle: '금액', valueAxisTitle: 'Users count', valueMin: 0 }), ONE)

    // then: x·y 축 제목과 y 최소가 설정대로다
    expect(get(b.options, 'scales', 'x', 'title', 'text')).toBe('금액')
    expect(get(b.options, 'scales', 'y', 'title', 'text')).toBe('Users count')
    expect(get(b.options, 'scales', 'y', 'min')).toBe(0)
  })

  // 테스트 코드: RC-065
  it('콤보의 범위는 기본 축에 적용한다', () => {
    // when: 최대값을 준 콤보를 만든다
    const b = build(chart({ kind: 'combo', values: [1, 2], valueMax: 4000, comboSeries: comboOf(2) }), ONE)

    // then: 기본 축 y의 최대가 설정과 같다
    expect(get(b.options, 'scales', 'y', 'max')).toBe(4000)
  })
})

describe('buildChart: 단위', () => {
  // 테스트 코드: RC-086
  it('금액 값은 원 그대로 그리고 나누지 않는다', () => {
    // when: 막대와 분산형을 만든다
    const actual = dataOf(build(chart(), ONE))
    const actual2 = dataOf(build(chart({ kind: 'scatter', values: [1, 2] }), ONE))[0]
    // then: 데이터가 원 단위 그대로다
    expect(actual).toEqual([3_000_000, 1_500_000, 500_000])
    expect(actual2).toEqual({ x: 3_000_000, y: 30 })
  })

  // 테스트 코드: RC-086
  it('건수로 집계한 금액 컬럼은 값을 바꾸지 않는다', () => {
    // given: 금액을 건수로 집계한 결과
    const counted = resultOf({ columns: [VENDOR, amount(1, 'count')], rows: [['Silverfort', 7], ['Okta', 3]] })

    // when: 막대를 만든다
    const actual = dataOf(build(chart(), counted))

    // then: 값이 그대로다
    expect(actual).toEqual([7, 3])
  })

  // 테스트 코드: RC-086
  it('단위가 없는 컬럼의 값은 그대로 둔다', () => {
    // when: Users count 컬럼으로 막대를 만든다
    const actual = dataOf(build(chart({ values: [2] }), ONE))

    // then: 값이 그대로다
    expect(actual).toEqual([30, 10, 5])
  })

  // 테스트 코드: RC-086
  it('금액 툴팁은 원 단위 콤마로 쓴다', () => {
    // given: 금액이 123,456,789인 차트
    const odd = resultOf({ columns: [VENDOR, amount(1)], rows: [['Silverfort', 123_456_789]] })
    const b = build(chart(), odd)
    const tooltip = get(b.options, 'plugins', 'tooltip', 'callbacks', 'label') as (c: unknown) => string

    // when: 툴팁 글자를 구한다
    const tip = tooltip({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 123_456_789, parsed: { x: 0, y: 123_456_789 }, label: 'Silverfort' })

    // then: 123,456,789가 들어 있다
    expect(tip).toContain('123,456,789')
  })

  // 테스트 코드: RC-086
  it('금액 데이터 레이블은 원 단위 콤마로 쓴다', () => {
    // given: 금액이 123,456,789이고 레이블을 켠 차트
    const odd = resultOf({ columns: [VENDOR, amount(1)], rows: [['Silverfort', 123_456_789]] })
    const b = build(chart({ dataLabels: true }), odd)
    const formatter = get(b.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    // when: 데이터 레이블 글자를 구한다
    const actual = formatter(123_456_789, { dataIndex: 0, datasetIndex: 0, dataset: b.data.datasets[0] })

    // then: 123,456,789다
    expect(actual).toBe('123,456,789')
  })

  // 테스트 코드: RC-086
  it('Users count 툴팁은 반올림한 정수로 쓴다', () => {
    // given: Users count 평균이 2.5인 차트
    const avg = resultOf({
      columns: [VENDOR, resultColumn({ index: 1, field: 'deal.users', label: 'Users count', type: 'number', valueType: 'decimal', format: null, unit: null, aggregate: 'avg' })],
      rows: [['Silverfort', 2.5]],
    })
    const b = build(chart(), avg)
    const tooltip = get(b.options, 'plugins', 'tooltip', 'callbacks', 'label') as (c: unknown) => string

    // when: 툴팁 글자를 구한다
    const tip = tooltip({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 2.5, parsed: { x: 0, y: 2.5 }, label: 'Silverfort' })

    // then: 3이 들어 있고 2.5는 없다
    expect(tip).toContain('3')
    expect(tip).not.toContain('2.5')
  })

  // 테스트 코드: RC-085
  it('툴팁 글자는 결과 표 칸과 같다', () => {
    // given: 금액 차트
    const b = build(chart(), ONE)
    const tooltip = get(b.options, 'plugins', 'tooltip', 'callbacks', 'label') as (c: unknown) => string

    // when: 툴팁 글자를 구한다
    const tip = tooltip({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 3_000_000, parsed: { x: 0, y: 3_000_000 }, label: 'Silverfort' })

    // then: 표 칸 글자가 들어 있다
    expect(tip).toContain(formatCell(3_000_000, amount(1), CTX))
  })
})

describe('buildChart: 그리지 못하는 경우', () => {
  const MISMATCH = '차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요'
  const TOO_MANY = '범주가 너무 많아 차트를 그리지 않습니다(최대 1,000개). 조건을 좁히세요'

  // 테스트 코드: RC-080
  it('범주가 결과의 그룹 열이 아니면 그리지 않는다', () => {
    // when: 그룹이 아닌 열을 범주로 준 차트를 만든다
    const actual = problemOf(chart({ category: 1 }), ONE)

    // then: "차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요"다
    expect(actual).toBe(MISMATCH)
  })

  // 테스트 코드: RC-080
  it('열 밖 index를 가리키면 그리지 않는다', () => {
    // when: 범주 또는 값이 결과 열 밖인다
    const actual = problemOf(chart({ category: 9 }), ONE)
    const actual2 = problemOf(chart({ values: [1, 9] }), ONE)
    // then: 둘 다 설정이 맞지 않는다는 문구다
    expect(actual).toBe(MISMATCH)
    expect(actual2).toBe(MISMATCH)
  })

  // 테스트 코드: RC-080
  it('값이 그룹 열이면 그리지 않는다', () => {
    // when: 그룹 열을 값으로 준 차트를 만든다
    const actual = problemOf(chart({ values: [0] }), ONE)

    // then: 설정이 맞지 않는다는 문구다
    expect(actual).toBe(MISMATCH)
  })

  const many = (categories: number, series = 1): ReportResult => {
    const rows: ReportCell[][] = []
    for (let c = 0; c < categories; c += 1) for (let s = 0; s < series; s += 1) rows.push([`c${c}`, `s${s}`, 1000])
    return resultOf({ columns: [VENDOR, STATUS, amount(2)], rows })
  }

  // 테스트 코드: RC-084
  it('점은 1,000개까지 그리고 1,001개부터는 그리지 않는다', () => {
    // given: 범주 1,000개/1,001개 결과를 쓰는 누적 막대 설정
    const at = chart({ kind: 'stacked_bar', series: 1, values: [2] })

    // when: 범주 1000개와 1001개 데이터의 문제 여부를 판정한다
    const actual = problemOf(at, many(1000))
    const actual2 = problemOf(at, many(1001))
    // then: 1,000개는 문제가 없고 1,001개는 "범주가 너무 많아…" 문구다
    expect(actual).toBeNull()
    expect(actual2).toBe(TOO_MANY)
  })

  // 테스트 코드: RC-084
  it('점 수는 범주 × 데이터셋으로 센다', () => {
    // given: 범주 2개 × 계열 500/501개 결과를 쓰는 누적 막대 설정
    const at = chart({ kind: 'stacked_bar', series: 1, values: [2] })

    // when: 계열 2개에 범주 500개와 501개 데이터의 문제 여부를 판정한다
    const actual = problemOf(at, many(2, 500))
    const actual2 = problemOf(at, many(2, 501))
    // then: 500개 계열은 문제가 없고 501개 계열은 점이 너무 많다는 문구다
    expect(actual).toBeNull()
    expect(actual2).toBe(TOO_MANY)
  })
})

describe('buildChart: 앞 N자는 축·범례 이름만 자른다', () => {
  const cut = (column: ReturnType<typeof resultColumn>, prefixLength: number) => ({ ...column, prefixLength })
  const NAMES = resultOf({
    columns: [cut(VENDOR, 3), cut(STATUS, 2), amount(2)],
    rows: [
      ['Alpha-1', 'Won', 3_000_000],
      ['Alpha-2', 'Open', 1_000_000],
      ['Alpha-2', 'Won', 2_000_000],
    ],
  })
  const tip = (b: Built, kind: 'title' | 'label') => get(b.options, 'plugins', 'tooltip', 'callbacks', kind) as (c: unknown) => unknown
  const text = (value: unknown): string => [value].flat().join('')

  // 테스트 코드: RC-083
  it('앞 N자는 범주 축 이름만 자르고 원래 값마다 한 자리를 둔다', () => {
    // when: 앞 3자로 자른 범주 열을 만든다
    const b = build(chart({ category: 0, values: [2] }), resultOf({ columns: [cut(VENDOR, 3), STATUS, amount(2)], rows: NAMES.rows }))

    // then: 축 이름은 잘린 이름이고 값은 원래 값마다 하나다
    expect(b.data.labels).toEqual(['Alp…', 'Alp…'])
    expect(dataOf(b)).toEqual([3_000_000, 2_000_000])
  })

  // 테스트 코드: RC-083
  it('앞 N자는 계열 범례 이름을 자른다', () => {
    // when: 앞 2자로 자른 계열 열로 누적 막대를 만든다
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2] }), NAMES)

    // then: 범례 이름이 잘린다
    expect(b.data.datasets.map((d) => d.label)).toEqual(['Wo…', 'Op…'])
  })

  // 테스트 코드: RC-083
  it('앞 N자는 원형의 범례 이름을 자른다', () => {
    // when: 앞 2자로 자른 범주 열로 원형을 만든다
    const b = build(chart({ kind: 'pie', values: [1] }), resultOf({ columns: [cut(VENDOR, 2), amount(1)], rows: [['Alpha-1', 3_000_000], ['Beta-1', 1_000_000]] }))

    // then: 범례 이름이 잘린다
    expect(b.data.labels).toEqual(['Al…', 'Be…'])
  })

  // 테스트 코드: RC-083
  it('툴팁 제목은 범주 전체 이름을 보인다', () => {
    // when: 앞 N자로 자른 열을 가진 누적 막대를 만든다
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2] }), NAMES)

    // then: 툴팁 제목이 전체 범주 이름이다
    expect(text(tip(b, 'title')([{ datasetIndex: 0, dataIndex: 0, label: 'Alp…' }]))).toBe('Alpha-1')
    expect(text(tip(b, 'title')([{ datasetIndex: 0, dataIndex: 1, label: 'Alp…' }]))).toBe('Alpha-2')
  })

  // 테스트 코드: RC-083
  it('툴팁은 값 앞에 전체 계열 이름을 보인다', () => {
    // given: 앞 N자로 자른 열을 가진 누적 막대
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2] }), NAMES)

    // when: 툴팁 글자를 구한다
    const label = tip(b, 'label')({ dataset: b.data.datasets[1], datasetIndex: 1, dataIndex: 1, raw: 1_000_000, parsed: { x: 0, y: 1_000_000 }, label: 'Alp…' })

    // then: "Open: 금액"처럼 전체 계열 이름이 앞에 있다
    expect(label).toBe(`Open: ${formatCell(1_000_000, amount(2), CTX)}`)
  })

  // 테스트 코드: RC-083
  it('원형 툴팁은 값 앞에 전체 범주 이름을 보인다', () => {
    // given: 앞 2자로 자른 범주 열의 원형
    const b = build(chart({ kind: 'pie', values: [1] }), resultOf({ columns: [cut(VENDOR, 2), amount(1)], rows: [['Alpha-1', 3_000_000], ['Beta-1', 1_000_000]] }))

    // when: 툴팁 글자를 구한다
    const label = tip(b, 'label')({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 3_000_000, parsed: 3_000_000, label: 'Al…' })

    // then: 전체 범주 이름으로 시작한다
    expect(String(label).startsWith('Alpha-1: ')).toBe(true)
  })

  // 테스트 코드: RC-083
  it('행/열을 바꿔도 잘린 이름과 전체 이름의 짝을 유지한다', () => {
    // when: 앞 N자로 자른 열을 행/열 전환해 만든다
    const b = build(chart({ kind: 'bar', series: 1, values: [2], swap: true }), NAMES)

    // then: 범주·데이터셋이 잘린 이름이고 툴팁은 전체 이름이다
    expect(b.data.labels).toEqual(['Wo…', 'Op…'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['Alp…', 'Alp…'])
    expect(text(tip(b, 'title')([{ datasetIndex: 0, dataIndex: 1, label: 'Op…' }]))).toBe('Open')
    expect(String(tip(b, 'label')({ dataset: b.data.datasets[1], datasetIndex: 1, dataIndex: 0, raw: 2_000_000, parsed: { x: 0, y: 2_000_000 }, label: 'Wo…' }))).toMatch(/^Alpha-2: /)
  })

  // 테스트 코드: RC-083
  it('값 열에 앞 N자가 있어도 데이터 레이블과 툴팁은 전체 값을 보인다', () => {
    // given: 앞 2자로 자른 값 열의 차트(레이블 켬)
    const b = build(chart({ values: [1], dataLabels: true }), resultOf({ columns: [VENDOR, cut(amount(1), 2)], rows: [['Silverfort', 3_000_000]] }))
    const formatter = get(b.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    // when: 데이터 레이블과 툴팁 글자를 구한다
    const shown = formatter(3_000_000, { dataIndex: 0, datasetIndex: 0, dataset: b.data.datasets[0] })
    const label = tip(b, 'label')({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 3_000_000, parsed: { x: 0, y: 3_000_000 }, label: 'Silverfort' })

    // then: 둘 다 3,000,000 전체 값이다
    expect(shown).toBe('3,000,000')
    expect(String(label).endsWith('3,000,000')).toBe(true)
  })

  // 테스트 코드: RC-083
  it('잘린 범주의 데이터 레이블은 전체 값이다', () => {
    // given: 앞 3자로 자른 범주 열의 차트(레이블 켬)
    const b = build(chart({ category: 0, values: [2], dataLabels: true }), resultOf({ columns: [cut(VENDOR, 3), STATUS, amount(2)], rows: NAMES.rows }))
    const formatter = get(b.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    // when: 데이터 레이블 글자를 구한다
    const actual = formatter(3_000_000, { dataIndex: 0, datasetIndex: 0, dataset: b.data.datasets[0] })

    // then: 3,000,000 전체 값이다
    expect(actual).toBe('3,000,000')
  })

  // 테스트 코드: RC-083
  it('분산형 툴팁의 점 이름은 전체 범주 이름이다', () => {
    // given: 앞 2자로 자른 범주 열의 분산형
    const b = build(chart({ kind: 'scatter', values: [1, 2] }), resultOf({ columns: [cut(VENDOR, 2), amount(1), users(2)], rows: [['Alpha-1', 3_000_000, 30]] }))

    // when: 툴팁 글자를 구한다
    const label = tip(b, 'label')({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: { x: 3_000_000, y: 30 }, parsed: { x: 3_000_000, y: 30 }, label: 'Alpha-1' })

    // then: 전체 이름으로 시작하고 점 이름 목록도 전체 이름이다
    expect(String(label).startsWith('Alpha-1: (')).toBe(true)
    expect(b.data.labels).toEqual(['Alpha-1'])
  })
})

describe('buildChart: 원 단위 축 눈금 단축', () => {
  const tickOf = (b: Built, axis: string): ((v: number) => string) | undefined =>
    get(b.options, 'scales', axis, 'ticks', 'callback') as ((v: number) => string) | undefined
  const MIXED = resultOf({ columns: [VENDOR, amount(1), users(2)], rows: [['Silverfort', 1_870_000_000, 30]] })

  // 테스트 코드: RC-086
  it('값 축에 금액만 올라간 세로 막대는 눈금을 억·만으로 줄인다', () => {
    // when: 금액 하나만 값으로 쓰는 막대를 만든다
    const b = build(chart(), ONE)

    // then: y 눈금이 18.7억·5,000만·9,000으로 표시된다
    expect(tickOf(b, 'y')?.(1_870_000_000)).toBe('18.7억')
    expect(tickOf(b, 'y')?.(50_000_000)).toBe('5,000만')
    expect(tickOf(b, 'y')?.(9_000)).toBe('9,000')
  })

  // 테스트 코드: RC-086
  it('가로 막대는 줄인 눈금을 x 축에 둔다', () => {
    // when: 가로 막대를 만든다
    const b = build(chart({ kind: 'horizontal_bar' }), ONE)

    // then: x 눈금이 줄어 있고 y에는 없다
    expect(tickOf(b, 'x')?.(100_000_000)).toBe('1억')
    expect(tickOf(b, 'y')).toBeUndefined()
  })

  // 테스트 코드: RC-086
  it.each(['stacked_bar', 'line', 'area'] as const)('누적 막대·꺾은선·영역도 눈금을 줄인다 (%s)', (kind) => {
    // when: 종류를 바꿔 만든다
    const actual = tickOf(build(chart({ kind }), ONE), 'y')?.(1_870_000_000)

    // then: y 눈금이 18.7억이다
    expect(actual).toBe('18.7억')
  })

  // 테스트 코드: RC-086
  it('금액이 다른 값과 같은 축에 있으면 눈금을 줄이지 않는다', () => {
    // when: 금액과 Users를 함께 값으로 쓰는 막대를 만든다
    const actual = tickOf(build(chart({ values: [1, 2] }), MIXED), 'y')

    // then: 눈금 함수가 없다
    expect(actual).toBeUndefined()
  })

  // 테스트 코드: RC-086
  it('단위 없는 값 열은 눈금을 줄이지 않는다', () => {
    // when: Users 열만 값으로 쓰는 막대를 만든다
    const actual = tickOf(build(chart({ values: [2] }), ONE), 'y')

    // then: 눈금 함수가 없다
    expect(actual).toBeUndefined()
  })

  // 테스트 코드: RC-086
  it('건수로 집계한 금액은 눈금을 줄이지 않는다', () => {
    // given: 금액을 건수로 집계한 결과
    const counted = resultOf({ columns: [VENDOR, amount(1, 'count')], rows: [['Silverfort', 7]] })

    // when: 막대를 만든다
    const actual = tickOf(build(chart(), counted), 'y')

    // then: 눈금 함수가 없다
    expect(actual).toBeUndefined()
  })

  // 테스트 코드: RC-086
  it('100% 누적은 % 눈금을 유지한다', () => {
    // when: 100% 누적 막대를 만든다
    const b = build(chart({ kind: 'stacked_100_bar', series: 1, values: [2] }), TWO)

    // then: y 눈금이 50%로 표시된다
    expect(tickOf(b, 'y')?.(50)).toBe('50%')
  })

  // 테스트 코드: RC-086
  it('콤보에서 금액 꺾은선만 있으면 보조 축 눈금만 줄인다', () => {
    // given: Users 막대와 금액 꺾은선 결과
    const lineAmount = resultOf({ columns: [VENDOR, users(1), amount(2)], rows: [['Silverfort', 30, 1_870_000_000]] })
    // when: 보조 축 꺾은선 콤보를 만든다
    const b = build(chart({ kind: 'combo', values: [1, 2], secondaryAxis: true, comboSeries: comboOf(2, true) }), lineAmount)

    // then: y에는 없고 y1 눈금만 18.7억으로 줄어 있다
    expect(tickOf(b, 'y')).toBeUndefined()
    expect(tickOf(b, 'y1')?.(1_870_000_000)).toBe('18.7억')
  })

  // 테스트 코드: RC-086
  it('콤보의 막대가 금액이고 꺾은선이 아니면 기본 축 눈금만 줄인다', () => {
    // when: 보조 축 꺾은선 콤보를 만든다 (전제: 막대는 금액, 꺾은선은 Users)
    const b = build(chart({ kind: 'combo', values: [1, 2], secondaryAxis: true, comboSeries: comboOf(2, true) }), ONE)

    // then: y 눈금이 줄어 있고 y1에는 없다
    expect(tickOf(b, 'y')?.(1_870_000_000)).toBe('18.7억')
    expect(tickOf(b, 'y1')).toBeUndefined()
  })

  // 테스트 코드: RC-086
  it('분산형은 x와 y 축을 따로 판정한다', () => {
    // when: 금액(x)과 Users(y) 분산형을 만든다
    const b = build(chart({ kind: 'scatter', values: [1, 2] }), ONE)

    // then: x 눈금만 줄어 있다
    expect(tickOf(b, 'x')?.(1_870_000_000)).toBe('18.7억')
    expect(tickOf(b, 'y')).toBeUndefined()
  })

  // 테스트 코드: RC-090
  it('원형은 축이 없다', () => {
    // when: 원형을 만든다
    const actual = build(chart({ kind: 'pie' }), ONE).options.scales

    // then: scales가 없다
    expect(actual).toBeUndefined()
  })
})
