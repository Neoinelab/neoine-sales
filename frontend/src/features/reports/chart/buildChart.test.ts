import { describe, expect, it } from 'vitest'
import { resultColumn, resultOf } from '../../../test/reportDesigner'
import type { ReportCell, ReportChartInput, ReportChartKind, ReportResult } from '../../../shared/model/reportTypes'
import { columnHeader, formatCell } from '../designer/format/formatCell'
import { buildChart } from './buildChart'

/**
 * `buildChart(input, result, ctx)`: 차트 설정(컬럼은 결과 열 index) + 조회 결과 → Chart.js에 넘길 값. 계획 4.8.4.
 * 반환: `{ type, data: { labels, datasets }, options } | { problem: string }`.
 * 계약(테스트가 정한 부분): 범주 이름은 data.labels(분산형도 점 이름으로 같은 자리), 툴팁은 options.plugins.tooltip.callbacks.label(context),
 * 데이터 레이블은 options.plugins.datalabels.formatter(value, { dataIndex, datasetIndex, dataset }).
 */

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }
const COLORS = ['#94a3b8', '#60a5fa', '#34d399', '#fbbf24', '#f472b6']

const VENDOR = resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', valueType: 'text', format: null, group: true })
const STATUS = resultColumn({ index: 1, field: 'deal.status', label: 'Status', type: 'code', valueType: 'text', format: null, group: true })
const amount = (index: number, aggregate: 'sum' | 'avg' | 'count' = 'sum') =>
  resultColumn({ index, field: 'deal.amount', label: '금액 합계', type: 'number', valueType: 'integer', format: null, unit: 'krw_thousand', aggregate })
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
    ...over,
  }
}

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

describe('buildChart: kind to Chart.js type and options (AC14)', () => {
  it('draws bar as a vertical bar chart', () => {
    const b = build(chart({ kind: 'bar' }), ONE)

    expect(b.type).toBe('bar')
    expect(get(b.options, 'indexAxis')).not.toBe('y')
    expect(get(b.options, 'scales', 'x', 'stacked')).toBeFalsy()
  })

  it('draws horizontal_bar with the index axis on y', () => {
    const b = build(chart({ kind: 'horizontal_bar' }), ONE)

    expect(b.type).toBe('bar')
    expect(get(b.options, 'indexAxis')).toBe('y')
  })

  it('stacks both axes for stacked_bar', () => {
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2], category: 0 }), TWO)

    expect(b.type).toBe('bar')
    expect(get(b.options, 'scales', 'x', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
  })

  it('stacks to 100 percent with a default maximum of 100', () => {
    const b = build(chart({ kind: 'stacked_100_bar', series: 1, values: [2] }), TWO)

    expect(get(b.options, 'scales', 'x', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'stacked')).toBe(true)
    expect(get(b.options, 'scales', 'y', 'max')).toBe(100)
  })

  it('draws line without fill and area with fill from the origin', () => {
    const line = build(chart({ kind: 'line' }), ONE)
    const area = build(chart({ kind: 'area' }), ONE)

    expect(line.type).toBe('line')
    expect(line.data.datasets.every((d) => d.fill === false)).toBe(true)
    expect(area.type).toBe('line')
    expect(area.data.datasets.every((d) => d.fill === 'origin')).toBe(true)
  })

  it.each<[ReportChartKind]>([['pie'], ['doughnut']])('draws %s as one dataset with a color per slice and no scales', (kind) => {
    const b = build(chart({ kind }), ONE)

    expect(b.type).toBe(kind)
    expect(b.data.datasets).toHaveLength(1)
    expect(b.data.datasets[0]?.backgroundColor).toEqual(COLORS.slice(0, 3))
    expect(b.options.scales).toBeUndefined()
  })

  it('draws scatter with the first value on x and the second on y, named by the category', () => {
    const b = build(chart({ kind: 'scatter', values: [1, 2] }), ONE)

    expect(b.type).toBe('scatter')
    expect(dataOf(b)).toEqual([
      { x: 3000, y: 30 },
      { x: 1500, y: 10 },
      { x: 500, y: 5 },
    ])
    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
  })

  it('draws combo as bars for the first value and lines for the others', () => {
    const b = build(chart({ kind: 'combo', values: [1, 2] }), ONE)

    expect(b.type).toBe('bar')
    expect(b.data.datasets[0]?.type).toBe('bar')
    expect(b.data.datasets[1]?.type).toBe('line')
    expect(b.data.datasets[1]?.yAxisID).toBeUndefined()
    expect(get(b.options, 'scales', 'y1')).toBeUndefined()
  })

  it('puts the lines of a combo on a right hand secondary axis', () => {
    const b = build(chart({ kind: 'combo', values: [1, 2], secondaryAxis: true }), ONE)

    expect(b.data.datasets[0]?.yAxisID).not.toBe('y1')
    expect(b.data.datasets[1]?.yAxisID).toBe('y1')
    expect(get(b.options, 'scales', 'y1', 'position')).toBe('right')
    expect(get(b.options, 'scales', 'y1', 'grid', 'drawOnChartArea')).toBe(false)
  })

  it('always sets responsive without a fixed aspect ratio', () => {
    const b = build(chart(), ONE)

    expect(b.options.responsive).toBe(true)
    expect(b.options.maintainAspectRatio).toBe(false)
  })
})

describe('buildChart: categories, series and values', () => {
  it('uses the categories in the order of first appearance and the value as one dataset', () => {
    const b = build(chart(), ONE)

    expect(b.data.labels).toEqual(['Silverfort', 'Okta', '(없음)'])
    expect(b.data.datasets).toHaveLength(1)
    expect(dataOf(b)).toEqual([3000, 1500, 500])
  })

  it('makes one dataset per value column named by the column header', () => {
    const b = build(chart({ values: [1, 2] }), ONE)

    expect(b.data.datasets.map((d) => d.label)).toEqual([columnHeader(amount(1)), 'Users count'])
    expect(dataOf(b, 1)).toEqual([30, 10, 5])
  })

  it('pivots a series column into one dataset per series value and fills missing cells with 0 for bars', () => {
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2] }), TWO)

    expect(b.data.labels).toEqual(['Silverfort', 'Okta'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['Won', 'Open'])
    expect(dataOf(b, 0)).toEqual([3000, 0])
    expect(dataOf(b, 1)).toEqual([1000, 2000])
  })

  it('leaves missing cells as null for line and area so the line breaks', () => {
    for (const kind of ['line', 'area'] as const) {
      const b = build(chart({ kind, series: 1, values: [2] }), TWO)

      expect(dataOf(b, 0)).toEqual([3000, null])
    }
  })

  it('swaps categories and datasets on transpose', () => {
    const b = build(chart({ kind: 'bar', series: 1, values: [2], swap: true }), TWO)

    expect(b.data.labels).toEqual(['Won', 'Open'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['Silverfort', 'Okta'])
    expect(dataOf(b, 0)).toEqual([3000, 1000])
    expect(dataOf(b, 1)).toEqual([0, 2000])
  })

  it('names an empty category value (none)', () => {
    expect(build(chart(), ONE).data.labels).toContain('(없음)')
  })

  it('writes category names like the result table does', () => {
    const date = resultColumn({ index: 0, field: 'deal.expected_close', label: 'Expected Close', type: 'date', valueType: 'date', format: 'weekday', group: true })
    const result = resultOf({ columns: [date, amount(1)], rows: [['2026-10-27', 1_000_000]] })

    const b = build(chart(), result)

    expect(b.data.labels).toEqual([formatCell('2026-10-27', date, CTX)])
    expect(b.data.labels[0]).toContain('화')
  })
})

describe('buildChart: 100 percent stacks', () => {
  it('turns every category into percentages of its own sum and 0 for an empty category', () => {
    const rows: ReportCell[][] = [...(TWO.rows as ReportCell[][]), ['Empty', 'Won', 0], ['Empty', 'Open', 0]]
    const result = { ...TWO, rows, totalCount: rows.length }

    const b = build(chart({ kind: 'stacked_100_bar', series: 1, values: [2] }), result)

    expect(b.data.labels).toEqual(['Silverfort', 'Okta', 'Empty'])
    expect(dataOf(b, 0)).toEqual([75, 0, 0])
    expect(dataOf(b, 1)).toEqual([25, 100, 0])
  })

  it('shows percent and the original value in the tooltip and percent in the data label', () => {
    const b = build(chart({ kind: 'stacked_100_bar', series: 1, values: [2], dataLabels: true }), TWO)
    const dataset = b.data.datasets[0]
    const tooltip = get(b.options, 'plugins', 'tooltip', 'callbacks', 'label') as (c: unknown) => string
    const formatter = get(b.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    const tip = tooltip({ dataset, datasetIndex: 0, dataIndex: 0, raw: 75, parsed: { x: 0, y: 75 }, label: 'Silverfort' })
    const label = formatter(75, { dataIndex: 0, datasetIndex: 0, dataset })

    expect(tip).toContain('75')
    expect(tip).toContain('3,000')
    expect(label).toMatch(/^75(\.0)?%$/)
  })
})

describe('buildChart: title, legend, labels, axes and range', () => {
  it('sets the title only when it is not empty', () => {
    expect(get(build(chart({ title: 'Vendor별 금액' }), ONE).options, 'plugins', 'title')).toMatchObject({ display: true, text: 'Vendor별 금액' })
    expect(get(build(chart({ title: '' }), ONE).options, 'plugins', 'title', 'display')).toBe(false)
  })

  it.each([
    ['top', true],
    ['right', true],
    ['bottom', true],
    ['none', false],
  ] as const)('sets the legend %s', (legend, display) => {
    const legendOptions = get(build(chart({ legend }), ONE).options, 'plugins', 'legend')

    expect(get(legendOptions, 'display')).toBe(display)
    if (display) expect(get(legendOptions, 'position')).toBe(legend)
  })

  it('switches the data labels with display and formats them like the table', () => {
    const on = build(chart({ dataLabels: true }), ONE)
    const off = build(chart({ dataLabels: false }), ONE)
    const formatter = get(on.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    expect(get(on.options, 'plugins', 'datalabels', 'display')).toBe(true)
    expect(get(off.options, 'plugins', 'datalabels', 'display')).toBe(false)
    expect(formatter(3000, { dataIndex: 0, datasetIndex: 0, dataset: on.data.datasets[0] })).toBe('3,000')
  })

  it('titles the category axis on x and the value axis on y for vertical charts, none when empty', () => {
    const titled = build(chart({ categoryAxisTitle: 'Vendor', valueAxisTitle: '금액 (천원)' }), ONE)
    const blank = build(chart(), ONE)

    expect(get(titled.options, 'scales', 'x', 'title')).toMatchObject({ display: true, text: 'Vendor' })
    expect(get(titled.options, 'scales', 'y', 'title')).toMatchObject({ display: true, text: '금액 (천원)' })
    expect(get(blank.options, 'scales', 'x', 'title', 'display')).toBeFalsy()
    expect(get(blank.options, 'scales', 'y', 'title', 'display')).toBeFalsy()
  })

  it('swaps the axes of a horizontal bar chart', () => {
    const b = build(chart({ kind: 'horizontal_bar', categoryAxisTitle: 'Vendor', valueAxisTitle: '금액', valueMin: 0, valueMax: 5000 }), ONE)

    expect(get(b.options, 'scales', 'y', 'title', 'text')).toBe('Vendor')
    expect(get(b.options, 'scales', 'x', 'title', 'text')).toBe('금액')
    expect(get(b.options, 'scales', 'x', 'min')).toBe(0)
    expect(get(b.options, 'scales', 'x', 'max')).toBe(5000)
  })

  it('sets the minimum and maximum of the value axis and leaves the keys out when null', () => {
    const ranged = build(chart({ valueMin: 0, valueMax: 5000 }), ONE)
    const auto = build(chart(), ONE)

    expect(get(ranged.options, 'scales', 'y', 'min')).toBe(0)
    expect(get(ranged.options, 'scales', 'y', 'max')).toBe(5000)
    expect('min' in (get(auto.options, 'scales', 'y') as object)).toBe(false)
    expect('max' in (get(auto.options, 'scales', 'y') as object)).toBe(false)
  })

  it('titles the first value on x and the second on y for scatter and ranges y', () => {
    const b = build(chart({ kind: 'scatter', values: [1, 2], categoryAxisTitle: '금액', valueAxisTitle: 'Users count', valueMin: 0 }), ONE)

    expect(get(b.options, 'scales', 'x', 'title', 'text')).toBe('금액')
    expect(get(b.options, 'scales', 'y', 'title', 'text')).toBe('Users count')
    expect(get(b.options, 'scales', 'y', 'min')).toBe(0)
  })

  it('ranges the primary axis of a combo chart', () => {
    const b = build(chart({ kind: 'combo', values: [1, 2], valueMax: 4000 }), ONE)

    expect(get(b.options, 'scales', 'y', 'max')).toBe(4000)
  })
})

describe('buildChart: units (AC15)', () => {
  it('divides amount-unit values by 1,000 (AC-6)', () => {
    expect(dataOf(build(chart(), ONE))).toEqual([3000, 1500, 500])
  })

  it('does not divide an amount column that is only counted', () => {
    const counted = resultOf({ columns: [VENDOR, amount(1, 'count')], rows: [['Silverfort', 7], ['Okta', 3]] })

    expect(dataOf(build(chart(), counted))).toEqual([7, 3])
  })

  it('leaves values of columns without a unit as they are', () => {
    expect(dataOf(build(chart({ values: [2] }), ONE))).toEqual([30, 10, 5])
  })

  it('writes the amount tooltip in rounded thousand won', () => {
    const odd = resultOf({ columns: [VENDOR, amount(1)], rows: [['Silverfort', 123_456_789]] })
    const b = build(chart(), odd)
    const tooltip = get(b.options, 'plugins', 'tooltip', 'callbacks', 'label') as (c: unknown) => string

    const tip = tooltip({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 123_456.789, parsed: { x: 0, y: 123_456.789 }, label: 'Silverfort' })

    expect(tip).toContain('123,457')
  })

  it('writes the Users count tooltip as a rounded whole number (AC-7)', () => {
    const avg = resultOf({
      columns: [VENDOR, resultColumn({ index: 1, field: 'deal.users', label: 'Users count', type: 'number', valueType: 'decimal', format: null, unit: null, aggregate: 'avg' })],
      rows: [['Silverfort', 2.5]],
    })
    const b = build(chart(), avg)
    const tooltip = get(b.options, 'plugins', 'tooltip', 'callbacks', 'label') as (c: unknown) => string

    const tip = tooltip({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 2.5, parsed: { x: 0, y: 2.5 }, label: 'Silverfort' })

    expect(tip).toContain('3')
    expect(tip).not.toContain('2.5')
  })

  it('writes the tooltip with the same text as the table cell', () => {
    const b = build(chart(), ONE)
    const tooltip = get(b.options, 'plugins', 'tooltip', 'callbacks', 'label') as (c: unknown) => string

    const tip = tooltip({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 3000, parsed: { x: 0, y: 3000 }, label: 'Silverfort' })

    expect(tip).toContain(formatCell(3_000_000, amount(1), CTX))
  })
})

describe('buildChart: problems (AC19, AC20)', () => {
  const MISMATCH = '차트 설정이 지금 결과와 맞지 않습니다. 편집에서 고치세요'
  const TOO_MANY = '범주가 너무 많아 차트를 그리지 않습니다(최대 1,000개). 조건을 좁히세요'

  it('reports a mismatch when the category is not a group column of the result', () => {
    expect(problemOf(chart({ category: 1 }), ONE)).toBe(MISMATCH)
  })

  it('reports a mismatch when an index is outside the result columns', () => {
    expect(problemOf(chart({ category: 9 }), ONE)).toBe(MISMATCH)
    expect(problemOf(chart({ values: [1, 9] }), ONE)).toBe(MISMATCH)
  })

  it('reports a mismatch when a value is a group column', () => {
    expect(problemOf(chart({ values: [0] }), ONE)).toBe(MISMATCH)
  })

  const many = (categories: number, series = 1): ReportResult => {
    const rows: ReportCell[][] = []
    for (let c = 0; c < categories; c += 1) for (let s = 0; s < series; s += 1) rows.push([`c${c}`, `s${s}`, 1000])
    return resultOf({ columns: [VENDOR, STATUS, amount(2)], rows })
  }

  it('draws 1,000 points but not 1,001', () => {
    const at = chart({ kind: 'stacked_bar', series: 1, values: [2] })

    expect(problemOf(at, many(1000))).toBeNull()
    expect(problemOf(at, many(1001))).toBe(TOO_MANY)
  })

  it('counts categories times datasets', () => {
    const at = chart({ kind: 'stacked_bar', series: 1, values: [2] })

    expect(problemOf(at, many(2, 500))).toBeNull()
    expect(problemOf(at, many(2, 501))).toBe(TOO_MANY)
  })
})

describe('buildChart: prefix length cuts axis and legend only (AC18, AC20)', () => {
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

  it('cuts the category axis labels but keeps one slot per original value', () => {
    const b = build(chart({ category: 0, values: [2] }), resultOf({ columns: [cut(VENDOR, 3), STATUS, amount(2)], rows: NAMES.rows }))

    expect(b.data.labels).toEqual(['Alp…', 'Alp…'])
    expect(dataOf(b)).toEqual([3000, 2000])
  })

  it('cuts the legend names of a series column', () => {
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2] }), NAMES)

    expect(b.data.datasets.map((d) => d.label)).toEqual(['Wo…', 'Op…'])
  })

  it('cuts the category legend of a pie chart', () => {
    const b = build(chart({ kind: 'pie', values: [2] }), resultOf({ columns: [cut(VENDOR, 2), STATUS, amount(2)], rows: [['Alpha-1', 'Won', 3_000_000], ['Beta-1', 'Open', 1_000_000]] }))

    expect(b.data.labels).toEqual(['Al…', 'Be…'])
  })

  it('shows the whole category name in the tooltip title', () => {
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2] }), NAMES)

    expect(text(tip(b, 'title')([{ datasetIndex: 0, dataIndex: 0, label: 'Alp…' }]))).toBe('Alpha-1')
    expect(text(tip(b, 'title')([{ datasetIndex: 0, dataIndex: 1, label: 'Alp…' }]))).toBe('Alpha-2')
  })

  it('shows the whole series name before the value in the tooltip', () => {
    const b = build(chart({ kind: 'stacked_bar', series: 1, values: [2] }), NAMES)

    const label = tip(b, 'label')({ dataset: b.data.datasets[1], datasetIndex: 1, dataIndex: 1, raw: 1000, parsed: { x: 0, y: 1000 }, label: 'Alp…' })

    expect(label).toBe(`Open: ${formatCell(1_000_000, amount(2), CTX)}`)
  })

  it('shows the whole category name before the value in a pie tooltip', () => {
    const b = build(chart({ kind: 'pie', values: [2] }), resultOf({ columns: [cut(VENDOR, 2), STATUS, amount(2)], rows: [['Alpha-1', 'Won', 3_000_000], ['Beta-1', 'Open', 1_000_000]] }))

    const label = tip(b, 'label')({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 3000, parsed: 3000, label: 'Al…' })

    expect(String(label).startsWith('Alpha-1: ')).toBe(true)
  })

  it('keeps cut and whole names paired when categories and datasets are swapped', () => {
    const b = build(chart({ kind: 'bar', series: 1, values: [2], swap: true }), NAMES)

    expect(b.data.labels).toEqual(['Wo…', 'Op…'])
    expect(b.data.datasets.map((d) => d.label)).toEqual(['Alp…', 'Alp…'])
    expect(text(tip(b, 'title')([{ datasetIndex: 0, dataIndex: 1, label: 'Op…' }]))).toBe('Open')
    expect(String(tip(b, 'label')({ dataset: b.data.datasets[1], datasetIndex: 1, dataIndex: 0, raw: 2000, parsed: { x: 0, y: 2000 }, label: 'Wo…' }))).toMatch(/^Alpha-2: /)
  })

  it('keeps the whole value in the data label and the tooltip when a value column has a prefix length', () => {
    const b = build(chart({ values: [1], dataLabels: true }), resultOf({ columns: [VENDOR, cut(amount(1), 2)], rows: [['Silverfort', 3_000_000]] }))
    const formatter = get(b.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    const shown = formatter(3000, { dataIndex: 0, datasetIndex: 0, dataset: b.data.datasets[0] })
    const label = tip(b, 'label')({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: 3000, parsed: { x: 0, y: 3000 }, label: 'Silverfort' })

    expect(shown).toBe('3,000')
    expect(String(label).endsWith('3,000')).toBe(true)
  })

  it('keeps the whole data label of a cut category', () => {
    const b = build(chart({ category: 0, values: [2], dataLabels: true }), resultOf({ columns: [cut(VENDOR, 3), STATUS, amount(2)], rows: NAMES.rows }))
    const formatter = get(b.options, 'plugins', 'datalabels', 'formatter') as (v: unknown, c: unknown) => string

    expect(formatter(3000, { dataIndex: 0, datasetIndex: 0, dataset: b.data.datasets[0] })).toBe('3,000')
  })

  it('names a scatter point by its whole category in the tooltip', () => {
    const b = build(chart({ kind: 'scatter', values: [1, 2] }), resultOf({ columns: [cut(VENDOR, 2), amount(1), users(2)], rows: [['Alpha-1', 3_000_000, 30]] }))

    const label = tip(b, 'label')({ dataset: b.data.datasets[0], datasetIndex: 0, dataIndex: 0, raw: { x: 3000, y: 30 }, parsed: { x: 3000, y: 30 }, label: 'Alpha-1' })

    expect(String(label).startsWith('Alpha-1: (')).toBe(true)
    expect(b.data.labels).toEqual(['Alpha-1'])
  })
})
