import { describe, expect, it } from 'vitest'
import type { DesignerState } from '../designer/state/designerState'
import { reduce, uidAt, withColumns } from '../../../test/reportDesigner'
import type { ReportChartInput } from '../../../shared/model/reportTypes'
import { chartDraftIssues, defaultChart, fromChartInput, normalizeForKind, toChartInput, type ChartDraft } from './chartDraft'

/**
 * Excel 확장의 차트 초안(Excel 확장 AC10, AC12, AC14). 기존 동작은 `chartDraft.test.ts`가 고정한다.
 * 계약(테스트가 정한 부분)
 * - `ChartDraft`에 `histogram: { mode: 'auto' | 'count' | 'width', count, width, overflow, underflow }`(입력 칸 문자열),
 *   `showTotal: boolean`, `comboTypes: Record<uid, { type, secondary }>`(값 열 uid 기준)가 있다.
 * - `defaultChart(columns, headerOf, isNumberField?)`: 그룹핑이 없고 숫자 필드(`isNumberField(field)`)가 있으면 히스토그램 초안,
 *   숫자 필드가 없거나 3개 이상 그룹이면 null. `isNumberField`를 생략하면 숫자 필드가 없는 것으로 본다.
 * - `toChartInput`: 종류가 쓰지 않는 옵션은 `histogram: null`·`showTotal: false`·`comboSeries: null`로 보낸다.
 *   구간 방식이 쓰지 않는 칸은 null로 보낸다(서버가 "비워 두세요"로 거절하지 않게). 잘못된 숫자 글자는 그대로 보낸다.
 * - `chartDraftIssues`의 `part`는 서버 위치를 '.'로 이은 것이다(`histogram.bin_count`, `combo_series`).
 */

function design(keys: string[], groups: number[]): DesignerState {
  let state = withColumns(...keys)
  for (const i of groups) state = reduce(state, { type: 'updateColumn', uid: uidAt(state, i), patch: { group: true } })
  return state
}

const headerOf = (uid: number): string => `H${uid}`
const isNumber = (field: string): boolean => ['deal.amount', 'deal.users'].includes(field)
/** Vendor(그룹, uid 1), 금액(2), Users(3), Status 체류(4). */
const ONE_GROUP = (): DesignerState => design(['deal.vendor', 'deal.amount', 'deal.users', 'deal.status_days'], [0])
/** Deal code(uid 1, 텍스트), 금액(2), Users(3): 그룹핑 없음. */
const UNGROUPED = (): DesignerState => withColumns('deal.code', 'deal.amount', 'deal.users')

const AUTO = { mode: 'auto', count: '', width: '', overflow: '', underflow: '' } as const

function draft(over: Partial<ChartDraft> = {}): ChartDraft {
  return {
    kind: 'bar',
    categoryUid: 1,
    seriesUid: null,
    valueUids: [2],
    swap: false,
    title: '',
    legend: 'top',
    dataLabels: false,
    categoryAxisTitle: '',
    valueAxisTitle: '',
    valueMin: '',
    valueMax: '',
    secondaryAxis: false,
    histogram: { ...AUTO },
    showTotal: false,
    comboTypes: {},
    ...over,
  }
}

describe('defaultChart: ungrouped report (AC10)', () => {
  it('starts a histogram of the first number column when there is no grouping', () => {
    const created = defaultChart(UNGROUPED().columns, headerOf, isNumber)

    expect(created).toMatchObject({ kind: 'histogram', categoryUid: null, seriesUid: null, valueUids: [2], histogram: AUTO })
  })

  it('cannot start a chart when no column is a number', () => {
    const text = withColumns('deal.code', 'deal.name')

    expect(defaultChart(text.columns, headerOf, isNumber)).toBeNull()
  })

  it('cannot start a chart without grouping when the number fields are unknown', () => {
    expect(defaultChart(UNGROUPED().columns, headerOf)).toBeNull()
  })

  it('still starts a vertical bar chart for one group column', () => {
    expect(defaultChart(ONE_GROUP().columns, headerOf, isNumber)).toMatchObject({ kind: 'bar', categoryUid: 1 })
  })
})

describe('normalizeForKind: new kinds', () => {
  it('clears the category and the series for the histogram and keeps one value', () => {
    const next = normalizeForKind(draft({ valueUids: [2, 3] }), 'histogram', ONE_GROUP().columns)

    expect(next).toMatchObject({ kind: 'histogram', categoryUid: null, seriesUid: null, valueUids: [2] })
  })

  it('gives the first group column back as the category when leaving the histogram', () => {
    const hist = draft({ kind: 'histogram', categoryUid: null })

    expect(normalizeForKind(hist, 'bar', ONE_GROUP().columns)).toMatchObject({ kind: 'bar', categoryUid: 1 })
  })

  it('keeps the category when moving between kinds that use one', () => {
    expect(normalizeForKind(draft({ categoryUid: 1 }), 'radar', ONE_GROUP().columns)).toMatchObject({ categoryUid: 1 })
  })

  it('starts a combo with a column first and lines for the rest', () => {
    const next = normalizeForKind(draft({ valueUids: [2, 3, 4] }), 'combo', ONE_GROUP().columns)

    expect(next.comboTypes).toEqual({
      2: { type: 'column', secondary: false },
      3: { type: 'line', secondary: false },
      4: { type: 'line', secondary: false },
    })
  })

  it('keeps the chosen combo types by value column uid', () => {
    const chosen = { 2: { type: 'area', secondary: false }, 3: { type: 'line', secondary: true } } as const
    const next = normalizeForKind(draft({ kind: 'combo', valueUids: [2, 3], comboTypes: { ...chosen } }), 'combo', ONE_GROUP().columns)

    expect(next.comboTypes).toEqual(chosen)
  })

  it('clears the total option outside the waterfall', () => {
    expect(normalizeForKind(draft({ kind: 'waterfall', showTotal: true }), 'bar', ONE_GROUP().columns).showTotal).toBe(false)
  })

  it('keeps the total option for the waterfall', () => {
    expect(normalizeForKind(draft({ kind: 'waterfall', showTotal: true }), 'waterfall', ONE_GROUP().columns).showTotal).toBe(true)
  })

  it('keeps up to three values for a bubble chart and one for a pareto chart', () => {
    const many = draft({ valueUids: [2, 3, 4] })

    expect(normalizeForKind(many, 'bubble', ONE_GROUP().columns).valueUids).toEqual([2, 3, 4])
    expect(normalizeForKind(many, 'pareto', ONE_GROUP().columns).valueUids).toEqual([2])
  })
})

describe('toChartInput and fromChartInput: new keys', () => {
  const columns = () => ONE_GROUP().columns

  it('sends no options for a kind that does not use them', () => {
    const input = toChartInput(draft({ histogram: { ...AUTO, mode: 'count', count: '5' }, showTotal: true, comboTypes: { 2: { type: 'area', secondary: true } } }), columns())

    expect(input).toMatchObject({ histogram: null, showTotal: false, comboSeries: null })
  })

  it('sends the bin setting of a histogram with the numbers parsed', () => {
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { mode: 'count', count: '8', width: '', overflow: '100.5', underflow: '' } })

    expect(toChartInput(hist, columns())).toMatchObject({
      category: null,
      histogram: { binMode: 'count', binCount: 8, binWidth: null, overflow: 100.5, underflow: null },
    })
  })

  it('sends only the field the bin mode uses', () => {
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { mode: 'width', count: '8', width: '2.5', overflow: '', underflow: '' } })

    expect(toChartInput(hist, columns()).histogram).toEqual({ binMode: 'width', binCount: null, binWidth: 2.5, overflow: null, underflow: null })
  })

  it('sends a bad number text as it is so the server answers with the position', () => {
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { mode: 'count', count: 'abc', width: '', overflow: '', underflow: '' } })

    expect(toChartInput(hist, columns()).histogram).toMatchObject({ binCount: 'abc' })
  })

  it('sends the total option only for the waterfall', () => {
    expect(toChartInput(draft({ kind: 'waterfall', showTotal: true }), columns())).toMatchObject({ showTotal: true })
  })

  it('sends the combo series in the order of the value columns and derives the secondary axis', () => {
    const combo = draft({
      kind: 'combo',
      valueUids: [3, 2],
      comboTypes: { 2: { type: 'line', secondary: true }, 3: { type: 'stacked_column', secondary: false } },
    })

    const input = toChartInput(combo, columns())

    expect(input.values).toEqual([2, 1])
    expect(input.comboSeries).toEqual([
      { type: 'stacked_column', secondary: false },
      { type: 'line', secondary: true },
    ])
    expect(input.secondaryAxis).toBe(true)
  })

  it('fills a missing combo setting with a column first and a line after', () => {
    const input = toChartInput(draft({ kind: 'combo', valueUids: [2, 3], comboTypes: {} }), columns())

    expect(input.comboSeries).toEqual([
      { type: 'column', secondary: false },
      { type: 'line', secondary: false },
    ])
    expect(input.secondaryAxis).toBe(false)
  })

  it('round trips a histogram input through the draft', () => {
    const input: ReportChartInput = {
      kind: 'histogram',
      category: null,
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
      histogram: { binMode: 'width', binCount: null, binWidth: 2.5, overflow: 100, underflow: -5 },
      showTotal: false,
      comboSeries: null,
    }

    const restored = fromChartInput(input, columns())

    expect(restored).toMatchObject({ categoryUid: null, histogram: { mode: 'width', width: '2.5', overflow: '100', underflow: '-5', count: '' } })
    expect(restored && toChartInput(restored, columns())).toEqual(input)
  })

  it('round trips a combo input and keys the settings by value column uid', () => {
    const input: ReportChartInput = {
      kind: 'combo',
      category: 0,
      series: null,
      values: [1, 2],
      swap: false,
      title: '',
      legend: 'top',
      dataLabels: false,
      categoryAxisTitle: '',
      valueAxisTitle: '',
      valueMin: null,
      valueMax: null,
      secondaryAxis: true,
      histogram: null,
      showTotal: false,
      comboSeries: [
        { type: 'stacked_area', secondary: false },
        { type: 'line_markers', secondary: true },
      ],
    }

    const restored = fromChartInput(input, columns())

    expect(restored?.comboTypes).toEqual({ 2: { type: 'stacked_area', secondary: false }, 3: { type: 'line_markers', secondary: true } })
    expect(restored && toChartInput(restored, columns())).toEqual(input)
  })

  it('round trips the total option of a waterfall', () => {
    const input = toChartInput(draft({ kind: 'waterfall', showTotal: true }), columns())

    const restored = fromChartInput(input, columns())

    expect(restored?.showTotal).toBe(true)
  })
})

describe('chartDraftIssues: new kinds', () => {
  const messages = (d: ChartDraft, state: DesignerState): string[] => chartDraftIssues(d, state.columns).map((i) => i.message)
  const issueAt = (d: ChartDraft, state: DesignerState, part: string): string | undefined => chartDraftIssues(d, state.columns).find((i) => i.part === part)?.message

  it('does not ask for a category for the histogram', () => {
    const hist = draft({ kind: 'histogram', categoryUid: null, valueUids: [2] })

    expect(chartDraftIssues(hist, UNGROUPED().columns).map((i) => i.part)).not.toContain('category')
  })

  it('is empty for a complete ungrouped histogram', () => {
    expect(chartDraftIssues(draft({ kind: 'histogram', categoryUid: null, valueUids: [2] }), UNGROUPED().columns)).toEqual([])
  })

  it.each([
    ['0', '구간 수는 1~100의 정수입니다'],
    ['101', '구간 수는 1~100의 정수입니다'],
    ['2.5', '구간 수는 1~100의 정수입니다'],
    ['', '구간 수는 1~100의 정수입니다'],
  ])('explains the bin count %j in count mode', (count, message) => {
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, mode: 'count', count } })

    expect(issueAt(hist, UNGROUPED(), 'histogram.bin_count')).toBe(message)
  })

  it.each(['1', '100'])('accepts the bin count %s', (count) => {
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, mode: 'count', count } })

    expect(issueAt(hist, UNGROUPED(), 'histogram.bin_count')).toBeUndefined()
  })

  it.each(['0', '-1', ''])('explains the bin width %j in width mode', (width) => {
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, mode: 'width', width } })

    expect(issueAt(hist, UNGROUPED(), 'histogram.bin_width')).toBe('구간 너비는 0보다 큰 숫자입니다')
  })

  it('does not check the count in auto or width mode', () => {
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, mode: 'width', width: '2', count: '0' } })

    expect(issueAt(hist, UNGROUPED(), 'histogram.bin_count')).toBeUndefined()
  })

  it('requires the overflow limit to exceed the underflow limit', () => {
    const hist = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, overflow: '10', underflow: '10' } })
    const ok = draft({ kind: 'histogram', categoryUid: null, histogram: { ...AUTO, overflow: '10', underflow: '9' } })

    expect(issueAt(hist, UNGROUPED(), 'histogram.overflow')).toBe('오버플로 구간은 언더플로 구간보다 커야 합니다')
    expect(issueAt(ok, UNGROUPED(), 'histogram.overflow')).toBeUndefined()
  })

  it('refuses a combo that puts every series on the secondary axis', () => {
    const combo = draft({
      kind: 'combo',
      valueUids: [2, 3],
      comboTypes: { 2: { type: 'column', secondary: true }, 3: { type: 'line', secondary: true } },
    })

    expect(issueAt(combo, ONE_GROUP(), 'combo_series')).toBe('모든 계열을 보조 축에 둘 수 없습니다')
  })

  it('checks the value count of the new kinds like the server', () => {
    expect(messages(draft({ kind: 'bubble', valueUids: [2, 3] }), ONE_GROUP())).toContain('이 차트는 값 열을 3개 골라야 합니다')
    expect(messages(draft({ kind: 'scatter_line', valueUids: [2] }), ONE_GROUP())).toContain('이 차트는 값 열을 2~10개 골라야 합니다')
  })
})
