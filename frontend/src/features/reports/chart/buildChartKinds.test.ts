import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportChartInput, ReportResult } from '../../../shared/model/reportTypes'
import { buildChart, CHART_MISMATCH, CHART_TOO_MANY } from './buildChart'

/**
 * 새 종류(23종)의 `buildChart` 계약(명세 RC-R44~RC-R56). 기존 10종은 `buildChart.test.ts`가 고정한다.
 * 계약(테스트가 정한 부분)
 * - `BuiltChart`에 `notes: string[]`가 있다(0 이하·빈 값 제외 개수 등 차트 아래 안내).
 * - 선(`line`·`radar`·`scatter_*`)의 표식은 데이터셋 `pointRadius`로 정한다: 0 = 표식 없음, 양수 = 표식.
 * - 누적은 막대·꺾은선·영역 모두 값 축 `stacked: true`이고 같은 누적 묶음은 같은 `stack` id를 쓴다.
 * - 폭포·히스토그램·파레토·깔때기는 `compute/` 순수 함수 결과로 그린다(함수 자체는 `compute/*.test.ts`).
 */

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }

const VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
const STATUS = resultColumn({ index: 1, field: 'deal.status', label: 'Status', type: 'code', valueType: 'text', format: null, group: true })
const sum = (index: number, field: string, label: string) =>
  resultColumn({ index, field, label, type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum' })
const amount = (index: number) =>
  resultColumn({ index, field: 'deal.amount', label: '금액 합계', type: 'number', valueType: 'integer', format: null, unit: 'krw', aggregate: 'sum' })
const users = (index: number) => sum(index, 'deal.users', 'Users count')

/** 그룹 1개 + 금액 + Users count + 점수. 마지막 Vendor는 값이 없다. */
const ONE: ReportResult = resultOf({
  columns: [VENDOR, amount(1), users(2), sum(3, 'deal.score', '점수')],
  rows: [
    ['Silverfort', 3_000_000, 30, 7],
    ['Okta', 1_500_000, 10, 5],
    [null, 500_000, 5, 1],
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

/** 그룹핑 없는 결과: 0 = Deal code(텍스트), 1 = Users(숫자 필드, 집계 없음). 값 0..10. */
const UNGROUPED: ReportResult = resultOf({
  columns: [
    resultColumn({ index: 0, field: 'deal.code', label: 'Deal code', type: 'text', valueType: 'text', format: null }),
    resultColumn({ index: 1, field: 'deal.users', label: 'Users', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: null }),
  ],
  rows: Array.from({ length: 11 }, (_, i) => [`D-${i}`, i]),
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
  notes: string[]
}

function build(input: ReportChartInput, result: ReportResult): Built {
  const built = buildChart(input, result, CTX) as unknown as Built | { problem: string }
  if ('problem' in built) throw new Error(`차트를 만들 수 없음: ${built.problem}`)
  return built
}
const problemOf = (input: ReportChartInput, result: ReportResult): string | null => (buildChart(input, result, CTX) as unknown as { problem?: string }).problem ?? null
const dataOf = (b: Built, i = 0): unknown[] => (b.data.datasets[i]?.data as unknown[]) ?? []

describe('buildChart: 가로 막대·세로 막대 변형', () => {
  // 테스트 코드: RC-087
  it('누적 가로 막대는 범주 축이 y이고 두 축을 모두 누적한다', () => {
    // when: 누적 가로 막대를 만든다
    const b = build(chart({ kind: 'stacked_horizontal_bar', series: 1, values: [2] }), TWO)

    // then: 종류는 bar, indexAxis는 y이고 x·y가 stacked다
    expect(b.type).toBe('bar')
    expect(get(b.options, 'indexAxis')).toBe('y')
    expect(get(b.options, 'scales', 'x', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
  })

  // 테스트 코드: RC-088
  it('100% 누적 가로 막대는 비율로 그리고 값 축(x) 최대가 100이다', () => {
    // when: 100% 누적 가로 막대를 만든다
    const b = build(chart({ kind: 'stacked_100_horizontal_bar', series: 1, values: [2] }), TWO)

    // then: indexAxis y, 범주별 비율 75/25와 0/100, x 최대 100이다
    expect(get(b.options, 'indexAxis')).toBe('y')
    expect(dataOf(b, 0)).toEqual([75, 0]) // Silverfort Won 3M / 4M, Okta Won 없음
    expect(dataOf(b, 1)).toEqual([25, 100])
    expect(get(b.options, 'scales', 'x', 'max')).toBe(100)
  })
})

describe('buildChart: 꺾은선 변형', () => {
  // 테스트 코드: RC-089
  it('꺾은선은 표식 없이, 표식이 있는 꺾은선은 표식과 함께 그린다', () => {
    // when: 꺾은선과 표식이 있는 꺾은선을 만든다
    const plain = build(chart({ kind: 'line' }), ONE)
    const marked = build(chart({ kind: 'line_markers' }), ONE)

    // then: 꺾은선은 pointRadius 0, 표식이 있는 꺾은선은 양수다
    expect(plain.type).toBe('line')
    expect(plain.data.datasets.every((d) => d.pointRadius === 0)).toBe(true)
    expect(marked.type).toBe('line')
    expect(marked.data.datasets.every((d) => typeof d.pointRadius === 'number' && d.pointRadius > 0)).toBe(true)
  })

  // 테스트 코드: RC-089
  it.each([
    ['stacked_line', 0],
    ['stacked_line_markers', 3],
  ] as const)('누적 꺾은선은 값 축을 한 묶음으로 누적하고 채우지 않는다 (%s)', (kind, radius) => {
    // when: 누적 꺾은선 종류를 만든다
    const b = build(chart({ kind, series: 1, values: [2] }), TWO)

    // then: 값 축이 stacked이고 stack id가 하나이며 fill false, 표식은 종류대로다
    expect(b.type).toBe('line')
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
    expect(new Set(b.data.datasets.map((d) => d.stack)).size).toBe(1)
    expect(b.data.datasets.every((d) => d.fill === false)).toBe(true)
    expect(b.data.datasets.every((d) => (radius === 0 ? d.pointRadius === 0 : Number(d.pointRadius) > 0))).toBe(true)
  })

  // 테스트 코드: RC-088
  it('100% 누적 꺾은선은 비율로 그리고 값 축을 0~100으로 둔다', () => {
    // when: 100% 누적 꺾은선을 만든다
    const b = build(chart({ kind: 'stacked_100_line', series: 1, values: [2] }), TWO)

    // then: 비율 75/25와 0/100, y가 stacked이고 최대 100이다
    expect(dataOf(b, 0)).toEqual([75, 0])
    expect(dataOf(b, 1)).toEqual([25, 100])
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'max')).toBe(100)
  })

  // 테스트 코드: RC-089
  it('누적 영역은 채워 누적하고 100% 누적 영역은 비율로 그린다', () => {
    // when: 누적 영역과 100% 누적 영역을 만든다
    const stacked = build(chart({ kind: 'stacked_area', series: 1, values: [2] }), TWO)
    const percent = build(chart({ kind: 'stacked_100_area', series: 1, values: [2] }), TWO)

    // then: 채움·누적·빈 칸 0이고 100%는 비율과 최대 100이다
    expect(stacked.type).toBe('line')
    expect(stacked.data.datasets.every((d) => d.fill && d.fill !== false)).toBe(true)
    expect(get(stacked.options, 'scales', 'y', 'stacked')).toBe(true)
    expect(dataOf(stacked, 0)).toEqual([3_000_000, 0]) // 누적은 빈 칸을 0으로 채운다
    expect(dataOf(percent, 1)).toEqual([25, 100])
    expect(get(percent.options, 'scales', 'y', 'max')).toBe(100)
  })

  // 테스트 코드: RC-084
  it('새 종류에도 점 1,000개 한도를 적용한다', () => {
    // given: 범주 1,001개 결과
    const rows = Array.from({ length: 1001 }, (_, i) => [`V${i}`, i + 1, 1, 1])
    const big = resultOf({ columns: ONE.columns, rows })

    // when: 누적 영역을 만든다
    const actual = problemOf(chart({ kind: 'stacked_area' }), big)

    // then: "범주가 너무 많아…" 문구다
    expect(actual).toBe(CHART_TOO_MANY)
  })
})

describe('buildChart: 분산형 변형과 거품형', () => {
  // 테스트 코드: RC-091
  it.each([
    ['scatter', false, 0, undefined],
    ['scatter_line_markers', true, 3, undefined],
    ['scatter_line', true, 0, undefined],
    ['scatter_smooth_markers', true, 3, 0.4],
    ['scatter_smooth', true, 0, 0.4],
  ] as const)('분산형 5종은 선·표식·곡선 설정대로 그린다 (%s)', (kind, line, radius, tension) => {
    // when: 분산형 종류를 만든다
    const b = build(chart({ kind, values: [1, 2] }), ONE)
    const d = b.data.datasets[0] as Record<string, unknown>

    // then: scatter 종류이고 showLine·pointRadius·tension이 종류대로다
    expect(b.type).toBe('scatter')
    expect(Boolean(d.showLine)).toBe(line)
    if (radius === 0 && line) expect(d.pointRadius).toBe(0)
    if (radius > 0) expect(Number(d.pointRadius)).toBeGreaterThan(0)
    if (tension !== undefined) expect(d.tension).toBe(tension)
    else expect(d.tension ?? 0).toBe(0)
  })

  // 테스트 코드: RC-091
  it('선이 있는 분산형은 결과 행 순서대로 점을 잇는다', () => {
    // when: 직선 분산형을 만든다
    const b = build(chart({ kind: 'scatter_line', values: [1, 2] }), ONE)

    // then: 점이 결과 행 순서대로 있다
    expect(dataOf(b)).toEqual([
      { x: 3_000_000, y: 30 },
      { x: 1_500_000, y: 10 },
      { x: 500_000, y: 5 },
    ])
  })

  // 테스트 코드: RC-091
  it('값 열이 더 있으면 첫 값 대비 y 계열이 하나씩 늘어난다', () => {
    // when: 값 3개로 분산형을 만든다
    const b = build(chart({ kind: 'scatter', values: [1, 2, 3] }), ONE)

    // then: 데이터셋 2개이고 각각 첫 값이 x, 값 열이 y다
    expect(b.data.datasets).toHaveLength(2)
    expect(dataOf(b, 0)).toEqual([
      { x: 3_000_000, y: 30 },
      { x: 1_500_000, y: 10 },
      { x: 500_000, y: 5 },
    ])
    expect(dataOf(b, 1)).toEqual([
      { x: 3_000_000, y: 7 },
      { x: 1_500_000, y: 5 },
      { x: 500_000, y: 1 },
    ])
  })

  // 테스트 코드: RC-091
  it('x나 y가 빈 행은 그 계열에서만 빠진다', () => {
    // given: x·y가 비어 있는 행을 가진 결과
    const gaps = resultOf({
      columns: ONE.columns,
      rows: [
        ['A', 100, 1, null],
        ['B', 200, null, 2],
      ],
    })

    // when: 값 3개로 분산형을 만든다
    const b = build(chart({ kind: 'scatter', values: [1, 2, 3] }), gaps)

    // then: 첫 계열은 첫 행만, 둘째 계열은 둘째 행만 남는다
    expect(dataOf(b, 0)).toEqual([{ x: 100, y: 1 }])
    expect(dataOf(b, 1)).toEqual([{ x: 200, y: 2 }])
  })

  // 테스트 코드: RC-092
  it('거품형은 셋째 값을 크기로, 면적이 크기에 비례하게 그린다', () => {
    // when: 값 3개로 거품형을 만든다
    const b = build(chart({ kind: 'bubble', values: [1, 2, 3] }), ONE)

    // then: 종류는 bubble, 점 x·y가 맞고 최대 크기는 반지름 30, 나머지는 4 + 26√비율이다
    expect(b.type).toBe('bubble')
    const points = dataOf(b) as { x: number; y: number; r: number }[]
    expect(points.map((p) => [p.x, p.y])).toEqual([
      [3_000_000, 30],
      [1_500_000, 10],
      [500_000, 5],
    ])
    expect(points[0]?.r).toBeCloseTo(30, 5) // 최대 크기(7)
    expect(points[1]?.r).toBeCloseTo(4 + 26 * Math.sqrt(5 / 7), 5)
  })

  // 테스트 코드: RC-092
  it('크기가 0 이하이거나 빈 거품은 그리지 않고 개수를 알린다', () => {
    // given: 크기가 4, 0, 빈 값인 결과
    const sizes = resultOf({
      columns: ONE.columns,
      rows: [
        ['A', 10, 1, 4],
        ['B', 20, 2, 0],
        ['C', 30, 3, null],
      ],
    })

    // when: 거품형을 만든다
    const b = build(chart({ kind: 'bubble', values: [1, 2, 3] }), sizes)

    // then: 점이 1개이고 안내에 "크기가 0 이하이거나 빈 값인 점 2개는 그리지 않았습니다"가 있다
    expect(dataOf(b)).toHaveLength(1)
    expect(b.notes).toContain('크기가 0 이하이거나 빈 값인 점 2개는 그리지 않았습니다')
  })

  // 테스트 코드: RC-092
  it('모든 거품을 그리면 안내가 없다', () => {
    // when: 값 3개로 거품형을 만든다
    const actual = build(chart({ kind: 'bubble', values: [1, 2, 3] }), ONE).notes

    // then: 안내가 비어 있다
    expect(actual).toEqual([])
  })

  // 테스트 코드: RC-080
  it('값이 정확히 3개가 아닌 거품형은 그리지 않는다', () => {
    // when: 값 2개로 거품형을 만든다
    const actual = problemOf(chart({ kind: 'bubble', values: [1, 2] }), ONE)

    // then: 설정이 맞지 않는다는 문구다
    expect(actual).toBe(CHART_MISMATCH)
  })
})

describe('buildChart: 방사형', () => {
  // 테스트 코드: RC-093
  it('방사형은 범주를 꼭짓점으로 반지름 축에 범위를 적용해 그린다', () => {
    // when: 범위를 준 방사형을 만든다
    const b = build(chart({ kind: 'radar', valueMin: 0, valueMax: 4_000_000 }), ONE)

    // then: 종류는 radar, 범주가 꼭짓점 이름이고 r 축 최소·최대가 설정과 같다
    expect(b.type).toBe('radar')
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(get(b.options, 'scales', 'r', 'min')).toBe(0)
    expect(get(b.options, 'scales', 'r', 'max')).toBe(4_000_000)
  })

  // 테스트 코드: RC-093
  it('표식은 표식이 있는 방사형만, 채움은 채워진 방사형만 있다', () => {
    // when: 방사형 세 종류를 만든다
    const plain = build(chart({ kind: 'radar' }), ONE)
    const marked = build(chart({ kind: 'radar_markers' }), ONE)
    const filled = build(chart({ kind: 'radar_filled' }), ONE)

    // then: 기본은 표식·채움 없음, 표식 종류는 표식, 채워진 종류는 반투명 채움이다
    expect(plain.data.datasets.every((d) => d.pointRadius === 0)).toBe(true)
    expect(marked.data.datasets.every((d) => Number(d.pointRadius) > 0)).toBe(true)
    expect(plain.data.datasets.every((d) => !d.fill)).toBe(true)
    expect(filled.data.datasets.every((d) => d.fill && d.fill !== false)).toBe(true)
    expect(String(filled.data.datasets[0]?.backgroundColor)).toMatch(/.{7}[0-9a-f]{2}$/i) // 반투명(알파 두 자리)
  })

  // 테스트 코드: RC-093
  it('그룹 2개 방사형은 계열마다 선을 하나씩 그린다', () => {
    // given: 범주 3개 이상인 두 그룹 결과
    const three = resultOf({
      columns: TWO.columns,
      rows: [['Silverfort', 'Won', 3_000_000], ['Silverfort', 'Open', 1_000_000], ['Okta', 'Open', 2_000_000], ['Ping', 'Won', 500_000]],
    })
    // when: 계열이 있는 방사형을 만든다
    const b = build(chart({ kind: 'radar', series: 1, values: [2] }), three)

    // then: 데이터셋 이름이 계열 값 순서다
    expect(b.data.datasets.map((d) => d.label)).toEqual(['Won', 'Open'])
  })

  // 테스트 코드: RC-093
  it('범주가 2개이면 계열이 있어도 방사형을 그리지 않는다', () => {
    // when: 범주 2개 결과로 계열이 있는 방사형을 만든다
    const actual = problemOf(chart({ kind: 'radar', series: 1, values: [2] }), TWO)

    // then: "방사형은 범주가 3개 이상일 때 그립니다"다
    expect(actual).toBe('방사형은 범주가 3개 이상일 때 그립니다')
  })

  // 테스트 코드: RC-093
  it('범주가 3개 미만이면 이유를 알리며 그리지 않는다', () => {
    // given: 범주 2개 결과
    const two = resultOf({ columns: ONE.columns, rows: [['A', 1, 1, 1], ['B', 2, 2, 2]] })

    // when: 방사형을 만든다
    const actual = problemOf(chart({ kind: 'radar' }), two)

    // then: "방사형은 범주가 3개 이상일 때 그립니다"다
    expect(actual).toBe('방사형은 범주가 3개 이상일 때 그립니다')
  })
})

describe('buildChart: 트리맵·선버스트', () => {
  // 테스트 코드: RC-094
  it('트리맵은 두 단계 트리를 플러그인에 넘기고 데이터 레이블은 끈다', () => {
    // when: 계열이 있는 트리맵을 만든다
    const b = build(chart({ kind: 'treemap', series: 1, values: [2] }), TWO)

    // then: 종류는 treemap, 트리가 상위·하위·값 행이고 데이터 레이블 display가 false다
    expect(b.type).toBe('treemap')
    const dataset = b.data.datasets[0] as { tree: Record<string, unknown>[]; groups: [string, string] }
    const [parent, child] = dataset.groups // 키 이름은 플러그인 예약 이름과만 겹치지 않으면 된다(buildTreemap.test.ts)
    expect(dataset.tree).toEqual([
      { [parent]: 'Silverfort', [child]: 'Won', value: 3_000_000 },
      { [parent]: 'Silverfort', [child]: 'Open', value: 1_000_000 },
      { [parent]: 'Okta', [child]: 'Open', value: 2_000_000 },
    ])
    expect(get(b.options, 'plugins', 'datalabels', 'display')).toBe(false)
  })

  // 테스트 코드: RC-096
  it('선버스트는 안쪽 상위 고리와 바깥 하위 고리 두 개의 도넛으로 그린다', () => {
    // when: 계열이 있는 선버스트를 만든다
    const b = build(chart({ kind: 'sunburst', series: 1, values: [2] }), TWO)

    // then: 종류는 doughnut, 데이터셋 2개이고 안쪽은 상위 합, 바깥은 하위 값이다
    expect(b.type).toBe('doughnut')
    expect(b.data.datasets).toHaveLength(2)
    expect(dataOf(b, 0)).toEqual([4_000_000, 2_000_000])
    expect(dataOf(b, 1)).toEqual([3_000_000, 1_000_000, 2_000_000])
  })

  // 테스트 코드: RC-097
  it('0 이하이거나 빈 칸은 그리지 않고 개수를 알린다', () => {
    // when: 계열이 있는 선버스트를 만든다
    const b = build(chart({ kind: 'sunburst', series: 1, values: [2] }), TWO)

    // then: 안내에 빠진 칸 1개가 있다
    expect(b.notes.join(' ')).toContain('1개') // Okta × Won은 칸이 비어 있다
  })
})

describe('buildChart: 히스토그램·파레토', () => {
  // 테스트 코드: RC-098
  it('그룹핑 없는 숫자 컬럼의 히스토그램은 구간 이름과 빈도 막대로 그린다', () => {
    // given: 구간 수 5개 설정
    const histogram = { binMode: 'count' as const, binCount: 5, binWidth: null, overflow: null, underflow: null }

    // when: 히스토그램을 만든다
    const b = build(chart({ kind: 'histogram', category: null, values: [1], histogram }), UNGROUPED)

    // then: 막대 종류이고 구간 이름이 5개이며 빈도가 3/2/2/2/2다
    expect(b.type).toBe('bar')
    expect(b.data.labels).toEqual(['[0, 2]', '(2, 4]', '(4, 6]', '(6, 8]', '(8, 10]'])
    expect(dataOf(b)).toEqual([3, 2, 2, 2, 2])
  })

  // 테스트 코드: RC-098
  it('구간 너비 방식이 구간을 너무 많이 만들면 너비를 늘리라고 알린다', () => {
    // given: 너비 0.001 방식 설정
    const histogram = { binMode: 'width' as const, binCount: null, binWidth: 0.001, overflow: null, underflow: null }

    // when: 히스토그램을 만든다
    const message = problemOf(chart({ kind: 'histogram', category: null, values: [1], histogram }), UNGROUPED)

    // then: "구간 너비를 늘리세요" 안내다
    expect(message).toContain('구간 너비를 늘리세요')
  })

  // 테스트 코드: RC-098
  it('집계 컬럼의 히스토그램은 그룹 값을 표본으로 센다', () => {
    // given: 구간 수 2개 설정
    const histogram = { binMode: 'count' as const, binCount: 2, binWidth: null, overflow: null, underflow: null }

    // when: 집계 컬럼으로 히스토그램을 만든다
    const b = build(chart({ kind: 'histogram', category: null, values: [2], histogram }), ONE)

    // then: 빈도 합이 그룹 수 3이다
    expect((dataOf(b) as number[]).reduce((a, c) => a + c, 0)).toBe(3) // 그룹 3개가 표본
  })

  // 테스트 코드: RC-098
  it('표본이 아무리 많아도 한도는 구간 수로 판정해 그린다', () => {
    // given: 표본 5,000개 결과와 자동 구간 설정
    const rows = Array.from({ length: 5000 }, (_, i) => [`D-${i}`, i % 97])
    const big = resultOf({ columns: UNGROUPED.columns, rows })
    const histogram = { binMode: 'auto' as const, binCount: null, binWidth: null, overflow: null, underflow: null }

    // when: 히스토그램을 만든다
    const built = buildChart(chart({ kind: 'histogram', category: null, values: [1], histogram }), big, CTX)

    // then: 문제 없이 그려진다
    expect('problem' in built).toBe(false)
  })

  // 테스트 코드: RC-098
  it('값 범위는 빈도 축에 적용한다', () => {
    // given: 자동 구간 설정
    const histogram = { binMode: 'auto' as const, binCount: null, binWidth: null, overflow: null, underflow: null }

    // when: 최대 50을 준 히스토그램을 만든다
    const b = build(chart({ kind: 'histogram', category: null, values: [1], histogram, valueMax: 50 }), UNGROUPED)

    // then: y 최대가 50이다
    expect(get(b.options, 'scales', 'y', 'max')).toBe(50)
  })

  // 테스트 코드: RC-101
  it('파레토는 내림차순 막대와 0~100% 보조 축 누적 꺾은선이다', () => {
    // when: 파레토를 만든다
    const b = build(chart({ kind: 'pareto' }), ONE)

    // then: 막대 내림차순, 누적 % 60/90/100 꺾은선이 y1(0~100, 오른쪽)에 있다
    expect(b.type).toBe('bar')
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(b.data.datasets[0]?.type).toBe('bar')
    expect(dataOf(b, 0)).toEqual([3_000_000, 1_500_000, 500_000])
    expect(b.data.datasets[1]?.type).toBe('line')
    expect(b.data.datasets[1]?.yAxisID).toBe('y1')
    expect(dataOf(b, 1)).toEqual([60, 90, 100])
    expect(get(b.options, 'scales', 'y1', 'min')).toBe(0)
    expect(get(b.options, 'scales', 'y1', 'max')).toBe(100)
    expect(get(b.options, 'scales', 'y1', 'position')).toBe('right')
  })

  // 테스트 코드: RC-101
  it('파레토는 리포트 정렬과 무관하게 내림차순이고 뺀 항목을 알린다', () => {
    // given: 정렬되지 않은 결과(값 0 포함)
    const unsorted = resultOf({
      columns: ONE.columns,
      rows: [['A', 10, 1, 1], ['B', 60, 1, 1], ['C', 0, 1, 1], ['D', 30, 1, 1]],
    })

    // when: 파레토를 만든다
    const b = build(chart({ kind: 'pareto' }), unsorted)

    // then: B, D, A 순서이고 안내에 빠진 항목 1개가 있다
    expect(b.data.labels).toEqual(['B', 'D', 'A'])
    expect(b.notes.join(' ')).toContain('1개')
  })
})

describe('buildChart: 폭포·깔때기', () => {
  // 테스트 코드: RC-102
  it('폭포는 앞 누계에서 떠 있는 막대이고 증가·감소·합계가 범례로 나뉜다', () => {
    // given: 증가·감소 값이 섞인 결과
    const mixed = resultOf({
      columns: ONE.columns,
      rows: [['A', 100, 1, 1], ['B', -40, 1, 1], ['C', 25, 1, 1]],
    })

    // when: 합계 막대를 켠 폭포를 만든다
    const b = build(chart({ kind: 'waterfall', showTotal: true }), mixed)

    // then: 범주 끝에 합계가 붙고 증가/감소/합계 데이터셋이 구간 값으로 채워진다
    expect(b.type).toBe('bar')
    expect(b.data.labels).toEqual(['A', 'B', 'C', '합계'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['증가', '감소', '합계'])
    expect(dataOf(b, 0)).toEqual([[0, 100], null, [60, 85], null])
    expect(dataOf(b, 1)).toEqual([null, [100, 60], null, null])
    expect(dataOf(b, 2)).toEqual([null, null, null, [0, 85]])
  })

  // 테스트 코드: RC-102
  it('합계 옵션이 없으면 합계 항목도 막대도 없다', () => {
    // when: 합계 없는 폭포를 만든다
    const b = build(chart({ kind: 'waterfall' }), ONE)

    // then: 범주에 합계가 없고 범례는 증가·감소뿐이다
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['증가', '감소'])
  })

  // 테스트 코드: RC-103
  it('깔때기는 가운데 정렬된 가로 막대이고 값 축을 숨긴다', () => {
    // when: 깔때기를 만든다
    const b = build(chart({ kind: 'funnel' }), ONE)

    // then: 막대 종류, indexAxis y, 막대가 [-값/2, 값/2]이며 x 축이 숨겨진다
    expect(b.type).toBe('bar')
    expect(get(b.options, 'indexAxis')).toBe('y')
    expect(dataOf(b)).toEqual([[-1_500_000, 1_500_000], [-750_000, 750_000], [-250_000, 250_000]])
    expect(get(b.options, 'scales', 'x', 'display')).toBe(false)
  })

  // 테스트 코드: RC-103
  it('깔때기는 0 이하 항목을 빼고 알린다', () => {
    // given: 값 0 항목이 있는 결과
    const zero = resultOf({ columns: ONE.columns, rows: [['A', 10, 1, 1], ['B', 0, 1, 1]] })

    // when: 깔때기를 만든다
    const b = build(chart({ kind: 'funnel' }), zero)

    // then: 범주에 0이 아닌 항목만 있고 안내에 빠진 항목 1개가 있다
    expect(b.data.labels).toEqual(['A'])
    expect(b.notes.join(' ')).toContain('1개')
  })
})

describe('buildChart: 콤보 계열별 설정', () => {
  const three = (comboSeries: ReportChartInput['comboSeries']) => chart({ kind: 'combo', values: [1, 2, 3], comboSeries })

  // 테스트 코드: RC-104
  it('콤보는 계열마다 종류를 그리고 보조 축 계열은 y1에 둔다', () => {
    // when: 막대·표식 꺾은선(보조 축)·영역 계열 콤보를 만든다
    const b = build(
      three([
        { type: 'column', secondary: false },
        { type: 'line_markers', secondary: true },
        { type: 'area', secondary: false },
      ]),
      ONE,
    )

    // then: 데이터셋 종류가 bar/line/line이고 보조 축 계열만 y1이며 영역은 채워진다
    expect(b.data.datasets.map((d) => d.type)).toEqual(['bar', 'line', 'line'])
    expect(b.data.datasets[1]?.yAxisID).toBe('y1')
    expect(Number(b.data.datasets[1]?.pointRadius)).toBeGreaterThan(0)
    expect(b.data.datasets[0]?.yAxisID).not.toBe('y1')
    expect(b.data.datasets[2]?.fill && b.data.datasets[2]?.fill !== false).toBe(true)
    expect(get(b.options, 'scales', 'y1', 'position')).toBe('right')
  })

  // 테스트 코드: RC-104
  it('같은 누적 종류는 한 묶음으로 누적하고 나머지는 따로 둔다', () => {
    // when: 누적 막대 둘과 막대 하나의 콤보를 만든다
    const b = build(
      three([
        { type: 'stacked_column', secondary: false },
        { type: 'stacked_column', secondary: false },
        { type: 'column', secondary: false },
      ]),
      ONE,
    )

    const stacks = b.data.datasets.map((d) => d.stack)
    // then: 누적 막대 둘은 bars 묶음, 막대는 다른 묶음이고 y가 stacked다
    expect(stacks[0]).toBe('bars')
    expect(stacks[1]).toBe('bars')
    expect(stacks[2]).not.toBe('bars')
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
  })

  // 테스트 코드: RC-104
  it('누적하지 않는 계열은 서로 다른 묶음 id를 가진다', () => {
    // when: 막대 둘과 꺾은선 하나의 콤보를 만든다
    const b = build(
      three([
        { type: 'column', secondary: false },
        { type: 'column', secondary: false },
        { type: 'line', secondary: false },
      ]),
      ONE,
    )

    // then: 두 막대의 stack id가 다르다
    expect(b.data.datasets[0]?.stack).not.toBe(b.data.datasets[1]?.stack)
  })

  // 테스트 코드: RC-104
  it('누적 영역은 areas 묶음이고 꺾은선이 막대 위에 그려진다', () => {
    // when: 누적 영역 둘과 막대 하나의 콤보를 만든다
    const b = build(
      three([
        { type: 'stacked_area', secondary: false },
        { type: 'stacked_area', secondary: false },
        { type: 'column', secondary: false },
      ]),
      ONE,
    )

    // then: 영역은 areas 묶음의 line, 막대는 bar다
    expect(b.data.datasets[0]?.stack).toBe('areas')
    expect(b.data.datasets[1]?.stack).toBe('areas')
    expect(b.data.datasets[0]?.type).toBe('line')
    expect(b.data.datasets[2]?.type).toBe('bar')
  })

  // 테스트 코드: RC-104
  it('서버가 옛 규칙으로 채운 계열 설정도 같은 모양으로 그린다', () => {
    // when: 첫 값 막대·나머지 보조 축 꺾은선 콤보를 만든다
    const b = build(three([{ type: 'column', secondary: false }, { type: 'line', secondary: true }, { type: 'line', secondary: true }]), ONE)

    // then: bar/line/line이고 둘째·셋째만 y1이다
    expect(b.data.datasets.map((d) => d.type)).toEqual(['bar', 'line', 'line'])
    expect(b.data.datasets.map((d) => d.yAxisID === 'y1')).toEqual([false, true, true])
  })
})

/**
 * 표식이 없는 종류(pointRadius 0)는 Chart.js 기본 상호작용(nearest + intersect)으로는 점 위 1px 안에서만 툴팁이 뜬다.
 * 계약: 빌더 결과의 `options.interaction`이 `intersect: false`이거나(꺾은선·영역·방사형은 `mode: 'index'`, 분산형은 `mode: 'nearest'`),
 * 표식 없는 모든 데이터셋의 `pointHitRadius`가 8 이상이다.
 */
describe('buildChart: 표식 없는 종류의 툴팁 적중 범위', () => {
  const ROUND_TRIP = [
    ['line', chart({ kind: 'line' }), ONE, 'index'],
    ['stacked_line', chart({ kind: 'stacked_line', series: 1, values: [2] }), TWO, 'index'],
    ['stacked_100_line', chart({ kind: 'stacked_100_line', series: 1, values: [2] }), TWO, 'index'],
    ['area', chart({ kind: 'area' }), ONE, 'index'],
    ['stacked_area', chart({ kind: 'stacked_area', series: 1, values: [2] }), TWO, 'index'],
    ['stacked_100_area', chart({ kind: 'stacked_100_area', series: 1, values: [2] }), TWO, 'index'],
    ['radar', chart({ kind: 'radar' }), ONE, 'index'],
    ['radar_filled', chart({ kind: 'radar_filled' }), ONE, 'index'],
    ['scatter_line', chart({ kind: 'scatter_line', values: [1, 2] }), ONE, 'nearest'],
    ['scatter_smooth', chart({ kind: 'scatter_smooth', values: [1, 2] }), ONE, 'nearest'],
    [
      'combo (line and area series)',
      chart({
        kind: 'combo',
        values: [1, 2, 3],
        comboSeries: [
          { type: 'column', secondary: false },
          { type: 'line', secondary: false },
          { type: 'stacked_area', secondary: false },
        ],
      }),
      ONE,
      'index',
    ],
  ] as const

  // 테스트 코드: RC-089
  it.each(ROUND_TRIP)('표식 없는 종류는 점 근처에서도 툴팁이 뜨게 한다 (%s)', (_name, input, result, mode) => {
    // when: 표식 없는 종류를 만든다
    const b = build(input, result)
    const interaction = get(b.options, 'interaction') as { mode?: string; intersect?: boolean } | undefined
    const bare = b.data.datasets.filter((d) => d.pointRadius === 0)
    const hitByRadius = bare.length > 0 && bare.every((d) => typeof d.pointHitRadius === 'number' && d.pointHitRadius >= 8)

    // then: interaction이 intersect false(꺾은선·영역·방사형 index, 분산형 nearest)이거나 점 적중 반경이 8 이상이다
    if (interaction) {
      expect(interaction.intersect).toBe(false)
      expect(interaction.mode).toBe(mode)
    } else {
      expect(hitByRadius).toBe(true)
    }
  })
})

/** 그룹핑 컬럼이 종류의 최대 수를 넘는 결과는 pivot이 행을 덮어쓰기 전에 그리지 않는다. */
describe('buildChart: 그룹핑 컬럼이 종류의 최대 수를 넘을 때', () => {
  const THREE: ReportResult = resultOf({
    columns: [VENDOR, STATUS, resultColumn({ index: 2, field: 'deal.forecast', label: 'Forecast', type: 'code', valueType: 'text', format: null, group: true }), amount(3)],
    rows: [
      ['Silverfort', 'Won', 'A', 3_000_000],
      ['Silverfort', 'Won', 'B', 1_000_000],
    ],
  })

  // 테스트 코드: RC-080
  it('그룹이 2개인 결과는 그룹 하나만 쓰는 원형을 그리지 않는다', () => {
    // when: 두 그룹 결과로 원형을 만든다
    const actual = problemOf(chart({ kind: 'pie', values: [2] }), TWO)

    // then: 설정이 맞지 않는다는 문구다
    expect(actual).toBe(CHART_MISMATCH)
  })

  // 테스트 코드: RC-080
  it('그룹 하나만 쓰는 깔때기에 계열이 있으면 그리지 않는다', () => {
    // when: 계열을 준 깔때기를 만든다
    const actual = problemOf(chart({ kind: 'funnel', series: 1, values: [2] }), TWO)

    // then: 설정이 맞지 않는다는 문구다
    expect(actual).toBe(CHART_MISMATCH)
  })

  // 테스트 코드: RC-080
  it('그룹이 3개인 결과는 막대를 그리지 않는다', () => {
    // when: 세 그룹 결과로 막대를 만든다
    const actual = problemOf(chart({ kind: 'bar', series: 1, values: [3] }), THREE)

    // then: 설정이 맞지 않는다는 문구다
    expect(actual).toBe(CHART_MISMATCH)
  })

  // 테스트 코드: RC-080
  it('그룹이 1개이면 원형을 그린다', () => {
    // when: 한 그룹 결과로 원형을 만든다
    const actual = problemOf(chart({ kind: 'pie' }), ONE)

    // then: 문제가 없다(null)
    expect(actual).toBeNull()
  })
})

/** 계열이 없으면(그룹 1개) 트리맵·선버스트에 값 열 머리글 이름의 자식 노드가 생기지 않는다. */
describe('buildChart: 계열 없는 트리맵·선버스트', () => {
  // 테스트 코드: RC-094
  it('계열이 없는 트리맵은 상위 한 단계로만 묶는다', () => {
    // when: 계열 없는 트리맵을 만든다
    const b = build(chart({ kind: 'treemap' }), ONE)
    const dataset = b.data.datasets[0] as { groups: string[]; tree: Record<string, unknown>[] }

    // then: groups가 upper 하나이고 상위 이름이 첫 등장 순이며 값 열 머리글 노드가 없다
    expect(dataset.groups).toEqual(['upper'])
    expect(dataset.tree.map((row) => row.upper)).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(dataset.tree.flatMap((row) => Object.values(row))).not.toContain('금액 합계')
  })

  // 테스트 코드: RC-094
  it('계열이 있는 트리맵은 두 단계를 유지한다', () => {
    // when: 계열이 있는 트리맵을 만든다
    const b = build(chart({ kind: 'treemap', series: 1, values: [2] }), TWO)
    const dataset = b.data.datasets[0] as { groups: string[] }

    // then: groups가 두 단계다
    expect(dataset.groups).toHaveLength(2)
  })

  // 테스트 코드: RC-096
  it('계열이 없는 선버스트는 상위 고리 하나로 그린다', () => {
    // when: 계열 없는 선버스트를 만든다
    const b = build(chart({ kind: 'sunburst' }), ONE)

    // then: 데이터셋 하나에 상위 합이 있고 범주 이름이 첫 등장 순이다
    expect(b.data.datasets).toHaveLength(1)
    expect(dataOf(b, 0)).toEqual([3_000_000, 1_500_000, 500_000])
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
  })

  // 테스트 코드: RC-096
  it('계열이 있는 선버스트는 고리 두 개를 유지한다', () => {
    // when: 계열이 있는 선버스트를 만든다
    const actual = build(chart({ kind: 'sunburst', series: 1, values: [2] }), TWO).data.datasets

    // then: 데이터셋이 2개다
    expect(actual).toHaveLength(2)
  })
})

/** 선버스트 바깥 고리 색은 앞 N자로 잘린 표시 이름이 아니라 상위 조각의 순번으로 정한다. */
describe('buildChart: 표시 이름이 같은 상위 범주의 선버스트 색', () => {
  const CUT_VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true, prefixLength: 5 })
  const CUT: ReportResult = resultOf({
    columns: [CUT_VENDOR, STATUS, amount(2)],
    rows: [
      ['Alpha-1', 'Won', 3],
      ['Alpha-1', 'Open', 2],
      ['Alpha-2', 'Won', 5],
      ['Alpha-2', 'Open', 4],
    ],
  })

  // 테스트 코드: RC-096
  it('앞 N자로 이름이 같아져도 바깥 고리 색은 상위 순번을 따른다', () => {
    // when: 앞 5자로 자른 상위 범주의 선버스트를 만든다
    const b = build(chart({ kind: 'sunburst', series: 1, values: [2] }), CUT)
    const inner = b.data.datasets[0]?.backgroundColor as string[]
    const outer = b.data.datasets[1]?.backgroundColor as string[]

    // then: 라벨은 하나뿐이어도 바깥 고리 색이 각 상위 색으로 시작한다
    expect(new Set(b.data.labels).size).toBe(1)
    expect(outer).toHaveLength(4)
    expect(outer[0]?.startsWith(inner[0] ?? '?')).toBe(true)
    expect(outer[1]?.startsWith(inner[0] ?? '?')).toBe(true)
    expect(outer[2]?.startsWith(inner[1] ?? '?')).toBe(true)
    expect(outer[3]?.startsWith(inner[1] ?? '?')).toBe(true)
  })
})

/** 구간 1,000개 한도는 일반 구간 수로만 판정한다(오버플로·언더플로 구간은 세지 않는다). */
describe('buildChart: 히스토그램 구간 한도', () => {
  const sample = (max: number): ReportResult =>
    resultOf({ columns: UNGROUPED.columns, rows: Array.from({ length: max + 1 }, (_, i) => [`D-${i}`, i]) })
  const width = (over: number | null, under: number | null) => ({ binMode: 'width' as const, binCount: null, binWidth: 1, overflow: over, underflow: under })

  // 테스트 코드: RC-098
  it('일반 구간 999개와 오버·언더플로 구간 둘을 그린다', () => {
    // given: 너비 1, 오버플로 5000, 언더플로 -5 설정과 표본 1,000개
    const histogram = width(5000, -5)

    // when: 히스토그램을 만든다
    const b = build(chart({ kind: 'histogram', category: null, values: [1], histogram }), sample(999))

    // then: 구간 이름이 1,001개다
    expect(b.data.labels).toHaveLength(1001)
  })

  // 테스트 코드: RC-098
  it('일반 구간이 1,001개이면 너비를 늘리라고 알리며 그리지 않는다', () => {
    // when: 구간 너비 1로 표본 1,002개의 히스토그램을 만든다
    const message = problemOf(chart({ kind: 'histogram', category: null, values: [1], histogram: width(null, null) }), sample(1001))

    // then: "구간 너비를 늘리세요" 안내다
    expect(message).toContain('구간 너비를 늘리세요')
  })
})
