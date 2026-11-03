import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportChartInput, ReportResult } from '../../../shared/model/reportTypes'
import { buildChart, CHART_MISMATCH, CHART_TOO_MANY } from './buildChart'

/**
 * Excel 확장으로 새로 생긴 종류(23종)의 `buildChart` 계약. 기존 10종은 `buildChart.test.ts`가 고정한다.
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
  it('stacks both axes of a stacked horizontal bar with the index axis on y', () => {
    const b = build(chart({ kind: 'stacked_horizontal_bar', series: 1, values: [2] }), TWO)

    expect(b.type).toBe('bar')
    expect(get(b.options, 'indexAxis')).toBe('y')
    expect(get(b.options, 'scales', 'x', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
  })

  it('draws a 100 percent stacked horizontal bar in percent with the value axis (x) up to 100', () => {
    const b = build(chart({ kind: 'stacked_100_horizontal_bar', series: 1, values: [2] }), TWO)

    expect(get(b.options, 'indexAxis')).toBe('y')
    expect(dataOf(b, 0)).toEqual([75, 0]) // Silverfort Won 3M / 4M, Okta Won 없음
    expect(dataOf(b, 1)).toEqual([25, 100])
    expect(get(b.options, 'scales', 'x', 'max')).toBe(100)
  })
})

describe('buildChart: 꺾은선 변형', () => {
  it('draws line without markers like Excel and line_markers with markers', () => {
    const plain = build(chart({ kind: 'line' }), ONE)
    const marked = build(chart({ kind: 'line_markers' }), ONE)

    expect(plain.type).toBe('line')
    expect(plain.data.datasets.every((d) => d.pointRadius === 0)).toBe(true)
    expect(marked.type).toBe('line')
    expect(marked.data.datasets.every((d) => typeof d.pointRadius === 'number' && d.pointRadius > 0)).toBe(true)
  })

  it.each([
    ['stacked_line', 0],
    ['stacked_line_markers', 3],
  ] as const)('stacks %s on the value axis in one stack and leaves no fill', (kind, radius) => {
    const b = build(chart({ kind, series: 1, values: [2] }), TWO)

    expect(b.type).toBe('line')
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
    expect(new Set(b.data.datasets.map((d) => d.stack)).size).toBe(1)
    expect(b.data.datasets.every((d) => d.fill === false)).toBe(true)
    expect(b.data.datasets.every((d) => (radius === 0 ? d.pointRadius === 0 : Number(d.pointRadius) > 0))).toBe(true)
  })

  it('draws a 100 percent stacked line in percent with a 0 to 100 axis', () => {
    const b = build(chart({ kind: 'stacked_100_line', series: 1, values: [2] }), TWO)

    expect(dataOf(b, 0)).toEqual([75, 0])
    expect(dataOf(b, 1)).toEqual([25, 100])
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'max')).toBe(100)
  })

  it('fills the stacked areas and stacks them, in percent for stacked_100_area', () => {
    const stacked = build(chart({ kind: 'stacked_area', series: 1, values: [2] }), TWO)
    const percent = build(chart({ kind: 'stacked_100_area', series: 1, values: [2] }), TWO)

    expect(stacked.type).toBe('line')
    expect(stacked.data.datasets.every((d) => d.fill && d.fill !== false)).toBe(true)
    expect(get(stacked.options, 'scales', 'y', 'stacked')).toBe(true)
    expect(dataOf(stacked, 0)).toEqual([3_000_000, 0]) // 누적은 빈 칸을 0으로 채운다
    expect(dataOf(percent, 1)).toEqual([25, 100])
    expect(get(percent.options, 'scales', 'y', 'max')).toBe(100)
  })

  it('applies the 1000 point limit to the new kinds too', () => {
    const rows = Array.from({ length: 1001 }, (_, i) => [`V${i}`, i + 1, 1, 1])
    const big = resultOf({ columns: ONE.columns, rows })

    expect(problemOf(chart({ kind: 'stacked_area' }), big)).toBe(CHART_TOO_MANY)
  })
})

describe('buildChart: 분산형 변형과 거품형', () => {
  it.each([
    ['scatter', false, 0, undefined],
    ['scatter_line_markers', true, 3, undefined],
    ['scatter_line', true, 0, undefined],
    ['scatter_smooth_markers', true, 3, 0.4],
    ['scatter_smooth', true, 0, 0.4],
  ] as const)('draws %s with line=%s, markers=%s and tension=%s', (kind, line, radius, tension) => {
    const b = build(chart({ kind, values: [1, 2] }), ONE)
    const d = b.data.datasets[0] as Record<string, unknown>

    expect(b.type).toBe('scatter')
    expect(Boolean(d.showLine)).toBe(line)
    if (radius === 0 && line) expect(d.pointRadius).toBe(0)
    if (radius > 0) expect(Number(d.pointRadius)).toBeGreaterThan(0)
    if (tension !== undefined) expect(d.tension).toBe(tension)
    else expect(d.tension ?? 0).toBe(0)
  })

  it('connects the points of a line variant in the order of the result rows', () => {
    const b = build(chart({ kind: 'scatter_line', values: [1, 2] }), ONE)

    expect(dataOf(b)).toEqual([
      { x: 3_000_000, y: 30 },
      { x: 1_500_000, y: 10 },
      { x: 500_000, y: 5 },
    ])
  })

  it('draws one y series per further value column against the first value as x', () => {
    const b = build(chart({ kind: 'scatter', values: [1, 2, 3] }), ONE)

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

  it('drops a row with an empty x or y only from that series', () => {
    const gaps = resultOf({
      columns: ONE.columns,
      rows: [
        ['A', 100, 1, null],
        ['B', 200, null, 2],
      ],
    })

    const b = build(chart({ kind: 'scatter', values: [1, 2, 3] }), gaps)

    expect(dataOf(b, 0)).toEqual([{ x: 100, y: 1 }])
    expect(dataOf(b, 1)).toEqual([{ x: 200, y: 2 }])
  })

  it('draws a bubble chart with the third value as the radius (area proportional to the size)', () => {
    const b = build(chart({ kind: 'bubble', values: [1, 2, 3] }), ONE)

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

  it('does not draw bubbles of size zero or less or empty and says how many', () => {
    const sizes = resultOf({
      columns: ONE.columns,
      rows: [
        ['A', 10, 1, 4],
        ['B', 20, 2, 0],
        ['C', 30, 3, null],
      ],
    })

    const b = build(chart({ kind: 'bubble', values: [1, 2, 3] }), sizes)

    expect(dataOf(b)).toHaveLength(1)
    expect(b.notes).toContain('크기가 0 이하이거나 빈 값인 점 2개는 그리지 않았습니다')
  })

  it('has no notes when every bubble is drawn', () => {
    expect(build(chart({ kind: 'bubble', values: [1, 2, 3] }), ONE).notes).toEqual([])
  })

  it('rejects a bubble chart that does not have exactly three values', () => {
    expect(problemOf(chart({ kind: 'bubble', values: [1, 2] }), ONE)).toBe(CHART_MISMATCH)
  })
})

describe('buildChart: 방사형', () => {
  it('draws the categories as axes on a radial scale with the value range', () => {
    const b = build(chart({ kind: 'radar', valueMin: 0, valueMax: 4_000_000 }), ONE)

    expect(b.type).toBe('radar')
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(get(b.options, 'scales', 'r', 'min')).toBe(0)
    expect(get(b.options, 'scales', 'r', 'max')).toBe(4_000_000)
  })

  it('shows markers only for radar_markers and fills only radar_filled', () => {
    const plain = build(chart({ kind: 'radar' }), ONE)
    const marked = build(chart({ kind: 'radar_markers' }), ONE)
    const filled = build(chart({ kind: 'radar_filled' }), ONE)

    expect(plain.data.datasets.every((d) => d.pointRadius === 0)).toBe(true)
    expect(marked.data.datasets.every((d) => Number(d.pointRadius) > 0)).toBe(true)
    expect(plain.data.datasets.every((d) => !d.fill)).toBe(true)
    expect(filled.data.datasets.every((d) => d.fill && d.fill !== false)).toBe(true)
    expect(String(filled.data.datasets[0]?.backgroundColor)).toMatch(/.{7}[0-9a-f]{2}$/i) // 반투명(알파 두 자리)
  })

  it('draws one line per series for two group columns with three or more categories', () => {
    const three = resultOf({
      columns: TWO.columns,
      rows: [['Silverfort', 'Won', 3_000_000], ['Silverfort', 'Open', 1_000_000], ['Okta', 'Open', 2_000_000], ['Ping', 'Won', 500_000]],
    })
    const b = build(chart({ kind: 'radar', series: 1, values: [2] }), three)

    expect(b.data.datasets.map((d) => d.label)).toEqual(['Won', 'Open'])
  })

  it('does not draw with two categories even when there is a series (AC8)', () => {
    expect(problemOf(chart({ kind: 'radar', series: 1, values: [2] }), TWO)).toBe('방사형은 범주가 3개 이상일 때 그립니다')
  })

  it('does not draw with fewer than three categories and explains why', () => {
    const two = resultOf({ columns: ONE.columns, rows: [['A', 1, 1, 1], ['B', 2, 2, 2]] })

    expect(problemOf(chart({ kind: 'radar' }), two)).toBe('방사형은 범주가 3개 이상일 때 그립니다')
  })
})

describe('buildChart: 트리맵·선버스트', () => {
  it('feeds the treemap plugin a two level tree and turns the data labels off', () => {
    const b = build(chart({ kind: 'treemap', series: 1, values: [2] }), TWO)

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

  it('draws a sunburst as two overlapping doughnut rings: parents inside, children outside', () => {
    const b = build(chart({ kind: 'sunburst', series: 1, values: [2] }), TWO)

    expect(b.type).toBe('doughnut')
    expect(b.data.datasets).toHaveLength(2)
    expect(dataOf(b, 0)).toEqual([4_000_000, 2_000_000])
    expect(dataOf(b, 1)).toEqual([3_000_000, 1_000_000, 2_000_000])
  })

  it('tells how many cells of zero or less or empty were not drawn', () => {
    const b = build(chart({ kind: 'sunburst', series: 1, values: [2] }), TWO)

    expect(b.notes.join(' ')).toContain('1개') // Okta × Won은 칸이 비어 있다
  })
})

describe('buildChart: 히스토그램·파레토', () => {
  it('draws the histogram of an ungrouped number column: bin names on the axis and counts as bars', () => {
    const histogram = { binMode: 'count' as const, binCount: 5, binWidth: null, overflow: null, underflow: null }

    const b = build(chart({ kind: 'histogram', category: null, values: [1], histogram }), UNGROUPED)

    expect(b.type).toBe('bar')
    expect(b.data.labels).toEqual(['[0, 2]', '(2, 4]', '(4, 6]', '(6, 8]', '(8, 10]'])
    expect(dataOf(b)).toEqual([3, 2, 2, 2, 2])
  })

  it('tells to widen the bin width when the width mode would need too many bins (not the generic too-many message)', () => {
    const histogram = { binMode: 'width' as const, binCount: null, binWidth: 0.001, overflow: null, underflow: null }

    const message = problemOf(chart({ kind: 'histogram', category: null, values: [1], histogram }), UNGROUPED)

    expect(message).toContain('구간 너비를 늘리세요')
  })

  it('draws the histogram of the group values of an aggregate column', () => {
    const histogram = { binMode: 'count' as const, binCount: 2, binWidth: null, overflow: null, underflow: null }

    const b = build(chart({ kind: 'histogram', category: null, values: [2], histogram }), ONE)

    expect((dataOf(b) as number[]).reduce((a, c) => a + c, 0)).toBe(3) // 그룹 3개가 표본
  })

  it('draws a very large ungrouped sample because the limit counts bins, not samples', () => {
    const rows = Array.from({ length: 5000 }, (_, i) => [`D-${i}`, i % 97])
    const big = resultOf({ columns: UNGROUPED.columns, rows })
    const histogram = { binMode: 'auto' as const, binCount: null, binWidth: null, overflow: null, underflow: null }

    const built = buildChart(chart({ kind: 'histogram', category: null, values: [1], histogram }), big, CTX)

    expect('problem' in built).toBe(false)
  })

  it('applies the value range to the frequency axis', () => {
    const histogram = { binMode: 'auto' as const, binCount: null, binWidth: null, overflow: null, underflow: null }

    const b = build(chart({ kind: 'histogram', category: null, values: [1], histogram, valueMax: 50 }), UNGROUPED)

    expect(get(b.options, 'scales', 'y', 'max')).toBe(50)
  })

  it('draws a pareto chart: bars descending and the cumulative percent as a line on a 0 to 100 secondary axis', () => {
    const b = build(chart({ kind: 'pareto' }), ONE)

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

  it('sorts the pareto bars descending whatever the sort of the report and notes the skipped items', () => {
    const unsorted = resultOf({
      columns: ONE.columns,
      rows: [['A', 10, 1, 1], ['B', 60, 1, 1], ['C', 0, 1, 1], ['D', 30, 1, 1]],
    })

    const b = build(chart({ kind: 'pareto' }), unsorted)

    expect(b.data.labels).toEqual(['B', 'D', 'A'])
    expect(b.notes.join(' ')).toContain('1개')
  })
})

describe('buildChart: 폭포·깔때기', () => {
  it('floats the bars from the running total and splits increase, decrease and total into legend entries', () => {
    const mixed = resultOf({
      columns: ONE.columns,
      rows: [['A', 100, 1, 1], ['B', -40, 1, 1], ['C', 25, 1, 1]],
    })

    const b = build(chart({ kind: 'waterfall', showTotal: true }), mixed)

    expect(b.type).toBe('bar')
    expect(b.data.labels).toEqual(['A', 'B', 'C', '합계'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['증가', '감소', '합계'])
    expect(dataOf(b, 0)).toEqual([[0, 100], null, [60, 85], null])
    expect(dataOf(b, 1)).toEqual([null, [100, 60], null, null])
    expect(dataOf(b, 2)).toEqual([null, null, null, [0, 85]])
  })

  it('has no total entry or bar without the total option', () => {
    const b = build(chart({ kind: 'waterfall' }), ONE)

    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['증가', '감소'])
  })

  it('draws a funnel as centered horizontal bars with the value axis hidden', () => {
    const b = build(chart({ kind: 'funnel' }), ONE)

    expect(b.type).toBe('bar')
    expect(get(b.options, 'indexAxis')).toBe('y')
    expect(dataOf(b)).toEqual([[-1_500_000, 1_500_000], [-750_000, 750_000], [-250_000, 250_000]])
    expect(get(b.options, 'scales', 'x', 'display')).toBe(false)
  })

  it('leaves out funnel items of zero or less and notes them', () => {
    const zero = resultOf({ columns: ONE.columns, rows: [['A', 10, 1, 1], ['B', 0, 1, 1]] })

    const b = build(chart({ kind: 'funnel' }), zero)

    expect(b.data.labels).toEqual(['A'])
    expect(b.notes.join(' ')).toContain('1개')
  })
})

describe('buildChart: 콤보 계열별 설정', () => {
  const three = (comboSeries: ReportChartInput['comboSeries']) => chart({ kind: 'combo', values: [1, 2, 3], comboSeries })

  it('draws each series with its own type and puts the secondary ones on y1', () => {
    const b = build(
      three([
        { type: 'column', secondary: false },
        { type: 'line_markers', secondary: true },
        { type: 'area', secondary: false },
      ]),
      ONE,
    )

    expect(b.data.datasets.map((d) => d.type)).toEqual(['bar', 'line', 'line'])
    expect(b.data.datasets[1]?.yAxisID).toBe('y1')
    expect(Number(b.data.datasets[1]?.pointRadius)).toBeGreaterThan(0)
    expect(b.data.datasets[0]?.yAxisID).not.toBe('y1')
    expect(b.data.datasets[2]?.fill && b.data.datasets[2]?.fill !== false).toBe(true)
    expect(get(b.options, 'scales', 'y1', 'position')).toBe('right')
  })

  it('stacks the stacked types of a kind in one stack and keeps the others unstacked from each other', () => {
    const b = build(
      three([
        { type: 'stacked_column', secondary: false },
        { type: 'stacked_column', secondary: false },
        { type: 'column', secondary: false },
      ]),
      ONE,
    )

    const stacks = b.data.datasets.map((d) => d.stack)
    expect(stacks[0]).toBe('bars')
    expect(stacks[1]).toBe('bars')
    expect(stacks[2]).not.toBe('bars')
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
  })

  it('gives unstacked series distinct stack ids so they do not pile up', () => {
    const b = build(
      three([
        { type: 'column', secondary: false },
        { type: 'column', secondary: false },
        { type: 'line', secondary: false },
      ]),
      ONE,
    )

    expect(b.data.datasets[0]?.stack).not.toBe(b.data.datasets[1]?.stack)
  })

  it('stacks stacked areas in the areas stack and draws lines above the bars', () => {
    const b = build(
      three([
        { type: 'stacked_area', secondary: false },
        { type: 'stacked_area', secondary: false },
        { type: 'column', secondary: false },
      ]),
      ONE,
    )

    expect(b.data.datasets[0]?.stack).toBe('areas')
    expect(b.data.datasets[1]?.stack).toBe('areas')
    expect(b.data.datasets[0]?.type).toBe('line')
    expect(b.data.datasets[2]?.type).toBe('bar')
  })

  it('keeps the legacy look for a series list that the server filled with the old rule', () => {
    const b = build(three([{ type: 'column', secondary: false }, { type: 'line', secondary: true }, { type: 'line', secondary: true }]), ONE)

    expect(b.data.datasets.map((d) => d.type)).toEqual(['bar', 'line', 'line'])
    expect(b.data.datasets.map((d) => d.yAxisID === 'y1')).toEqual([false, true, true])
  })
})
