import { describe, expect, it } from 'vitest'
import { designerReducer, type DesignerState } from '../designer/state/designerState'
import { emptyDesign, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../test/reportDesigner'
import type { ReportChartInput, ReportChartKind } from '../../../shared/model/reportTypes'
import { CHART_KINDS } from './chartKinds'
import { chartDraftIssues, defaultChart, fromChartInput, normalizeForKind, reconcileChart, toChartInput, type ChartDraft } from './chartDraft'

/**
 * 차트 초안(화면 상태, 컬럼은 uid로 가리킨다)의 순수 함수. 계획 4.8.2.
 * 시그니처(테스트가 정한 계약):
 *   defaultChart(columns, headerOf: (uid) => string): ChartDraft | null   그룹핑 1~2개가 아니면 null
 *   normalizeForKind(draft, kind, columns): ChartDraft
 *   reconcileChart(draft | null, columns): ChartDraft | null
 *   toChartInput(draft, columns): 요청 모양(참조가 없으면 null, 숫자 칸이 잘못되면 글자 그대로)
 *   fromChartInput(input | null, columns): ChartDraft | null   index → uid, 범위 밖 index는 참조 없음
 *   chartDraftIssues(draft, columns): { part, message }[]
 */

/** key 목록으로 컬럼을 추가하고, group에 든 index의 컬럼을 그룹핑한다(집계는 카탈로그 기본값이 채워진다). */
function design(keys: string[], groups: number[]): DesignerState {
  let state = withColumns(...keys)
  for (const i of groups) state = reduce(state, { type: 'updateColumn', uid: uidAt(state, i), patch: { group: true } })
  return state
}

const HEADERS: Record<number, string> = { 1: 'Vendor', 2: 'Status', 3: '금액 합계 (천원)', 4: 'Users count 합계' }
const headerOf = (uid: number): string => HEADERS[uid] ?? ''
/** ONE_GROUP 설계의 uid 기준 머리글(Vendor 1, 금액 2, Users count 3, Status 체류 4). */
const ONE_GROUP_HEADERS: Record<number, string> = { 1: 'Vendor', 2: '금액 합계 (천원)', 3: 'Users count 합계', 4: 'Status 체류 합계' }
const oneGroupHeaderOf = (uid: number): string => ONE_GROUP_HEADERS[uid] ?? ''

/** Vendor(그룹, uid 1), 금액(2), Users(3), Status 체류(4)로 이루어진 1그룹 설계. */
const ONE_GROUP = (): DesignerState => design(['deal.vendor', 'deal.amount', 'deal.users', 'deal.status_days'], [0])
/** Vendor(1), Status(2) 그룹 + 금액(3), Users(4). */
const TWO_GROUPS = (): DesignerState => design(['deal.vendor', 'deal.status', 'deal.amount', 'deal.users'], [0, 1])

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
    ...over,
  }
}

describe('defaultChart (AC12)', () => {
  it('starts a vertical bar chart for one group column with the headers as axis titles', () => {
    const created = defaultChart(ONE_GROUP().columns, oneGroupHeaderOf)

    expect(created).toEqual({
      kind: 'bar',
      categoryUid: 1,
      seriesUid: null,
      valueUids: [2],
      swap: false,
      title: '',
      legend: 'top',
      dataLabels: false,
      categoryAxisTitle: 'Vendor',
      valueAxisTitle: '금액 합계 (천원)',
      valueMin: '',
      valueMax: '',
      secondaryAxis: false,
    })
  })

  it('starts a stacked bar chart for two group columns with the second one as series', () => {
    const created = defaultChart(TWO_GROUPS().columns, headerOf)

    expect(created).toMatchObject({ kind: 'stacked_bar', categoryUid: 1, seriesUid: 2, valueUids: [3], categoryAxisTitle: 'Vendor', valueAxisTitle: '금액 합계 (천원)' })
  })

  it('cannot start a chart without group columns or with three or more', () => {
    const none = withColumns('deal.code', 'deal.name')
    const three = design(['deal.vendor', 'deal.status', 'deal.forecast', 'deal.amount'], [0, 1, 2])

    expect(defaultChart(none.columns, headerOf)).toBeNull()
    expect(defaultChart(three.columns, headerOf)).toBeNull()
  })

  it('leaves the value empty when no aggregate column exists', () => {
    const onlyGroup = design(['deal.vendor'], [0])

    expect(defaultChart(onlyGroup.columns, headerOf)).toMatchObject({ kind: 'bar', categoryUid: 1, valueUids: [] })
  })
})

describe('normalizeForKind (AC13)', () => {
  const rich = () => draft({ kind: 'bar', valueUids: [2, 3, 4], swap: true, secondaryAxis: true, valueMin: '1', valueMax: '9', title: '제목' })

  it.each<ReportChartKind>(['pie', 'doughnut'])('keeps one value, no series, no swap, no secondary axis and no range for %s', (kind) => {
    const next = normalizeForKind(rich(), kind, ONE_GROUP().columns)

    expect(next).toMatchObject({ kind, seriesUid: null, valueUids: [2], swap: false, secondaryAxis: false, valueMin: '', valueMax: '', title: '제목', categoryUid: 1 })
  })

  it('keeps two values and the range for scatter but drops swap and the secondary axis', () => {
    const next = normalizeForKind(rich(), 'scatter', ONE_GROUP().columns)

    expect(next).toMatchObject({ kind: 'scatter', valueUids: [2, 3], swap: false, secondaryAxis: false, valueMin: '1', valueMax: '9' })
  })

  it('keeps every value and the secondary axis for combo but drops swap', () => {
    const next = normalizeForKind(rich(), 'combo', ONE_GROUP().columns)

    expect(next).toMatchObject({ kind: 'combo', valueUids: [2, 3, 4], swap: false, secondaryAxis: true, valueMin: '1', valueMax: '9' })
  })

  it.each<ReportChartKind>(['bar', 'horizontal_bar', 'stacked_bar', 'stacked_100_bar', 'line', 'area'])('keeps swap, values and range but drops the secondary axis for %s', (kind) => {
    const next = normalizeForKind(draft({ kind: 'pie', valueUids: [2, 3], swap: true, secondaryAxis: true, valueMin: '1', valueMax: '9' }), kind, ONE_GROUP().columns)

    expect(next).toMatchObject({ kind, valueUids: [2, 3], swap: true, secondaryAxis: false, valueMin: '1', valueMax: '9' })
  })

  it('fills the free group column as series when moving from a one-series kind to a stacked kind', () => {
    const pie = draft({ kind: 'pie', categoryUid: 1, seriesUid: null, valueUids: [3] })

    expect(normalizeForKind(pie, 'stacked_bar', TWO_GROUPS().columns)).toMatchObject({ kind: 'stacked_bar', categoryUid: 1, seriesUid: 2 })
  })

  it('drops the series when the kind has none', () => {
    const stacked = draft({ kind: 'stacked_bar', seriesUid: 2, valueUids: [3] })

    expect(normalizeForKind(stacked, 'combo', TWO_GROUPS().columns).seriesUid).toBeNull()
  })

  it.each(CHART_KINDS.map((k) => k.key))('always leaves a draft that follows the rule table of %s', (kind) => {
    const rule = CHART_KINDS.find((k) => k.key === kind)
    if (!rule) throw new Error('rule')

    const next = normalizeForKind(rich(), kind, ONE_GROUP().columns)

    expect(next.kind).toBe(kind)
    expect(next.valueUids.length).toBeLessThanOrEqual(rule.valuesMax)
    if (!rule.allowsSwap) expect(next.swap).toBe(false)
    if (!rule.allowsSecondary) expect(next.secondaryAxis).toBe(false)
    if (!rule.allowsValueRange) expect([next.valueMin, next.valueMax]).toEqual(['', ''])
    if (!rule.allowsSeries) expect(next.seriesUid).toBeNull()
  })
})

describe('reconcileChart (AC17)', () => {
  it('drops a removed value column and keeps the rest of the settings', () => {
    const before = ONE_GROUP()
    const chart = draft({ valueUids: [2, 3], title: '제목' })
    const after = designerReducer(before, { type: 'removeColumn', uid: 3 }, REPORT_CATALOG)

    expect(reconcileChart(chart, after.columns)).toEqual({ ...chart, valueUids: [2] })
  })

  it('clears the category when its grouping is turned off', () => {
    const after = designerReducer(ONE_GROUP(), { type: 'updateColumn', uid: 1, patch: { group: false } }, REPORT_CATALOG)

    expect(reconcileChart(draft({ title: '남는 제목' }), after.columns)).toMatchObject({ categoryUid: null, title: '남는 제목' })
  })

  it('clears the series when its grouping is turned off and keeps the category', () => {
    const before = TWO_GROUPS()
    const after = designerReducer(before, { type: 'updateColumn', uid: 2, patch: { group: false } }, REPORT_CATALOG)

    expect(reconcileChart(draft({ kind: 'stacked_bar', seriesUid: 2, valueUids: [3] }), after.columns)).toMatchObject({ categoryUid: 1, seriesUid: null })
  })

  it('drops a value column that became a group column', () => {
    const after = designerReducer(ONE_GROUP(), { type: 'updateColumn', uid: 3, patch: { group: true } }, REPORT_CATALOG)

    expect(reconcileChart(draft({ valueUids: [2, 3] }), after.columns)?.valueUids).toEqual([2])
  })

  it('clears a column that was removed from the category', () => {
    const after = designerReducer(ONE_GROUP(), { type: 'removeColumn', uid: 1 }, REPORT_CATALOG)

    expect(reconcileChart(draft(), after.columns)?.categoryUid).toBeNull()
  })

  it('follows moved columns by uid so the request indexes change with the order', () => {
    const before = ONE_GROUP()
    const chart = draft({ valueUids: [3] })
    const moved = designerReducer(before, { type: 'moveColumn', uid: 3, to: 0 }, REPORT_CATALOG)

    expect(reconcileChart(chart, moved.columns)).toEqual(chart)
    expect(toChartInput(chart, before.columns)).toMatchObject({ category: 0, values: [2] })
    expect(toChartInput(chart, moved.columns)).toMatchObject({ category: 1, values: [0] })
  })

  it('passes null through', () => {
    expect(reconcileChart(null, ONE_GROUP().columns)).toBeNull()
  })
})

describe('chart input and draft (AC18)', () => {
  const INPUT: ReportChartInput = {
    kind: 'stacked_bar',
    category: 0,
    series: 1,
    values: [2],
    swap: true,
    title: '분기 Pipeline',
    legend: 'right',
    dataLabels: true,
    categoryAxisTitle: 'Vendor',
    valueAxisTitle: '금액',
    valueMin: 0,
    valueMax: 12.5,
    secondaryAxis: false,
  }

  it('round trips a chart input through the draft', () => {
    const columns = TWO_GROUPS().columns

    const restored = fromChartInput(INPUT, columns)

    expect(restored).toMatchObject({ categoryUid: 1, seriesUid: 2, valueUids: [3], valueMin: '0', valueMax: '12.5' })
    expect(restored && toChartInput(restored, columns)).toEqual(INPUT)
  })

  it('round trips null range and a negative minimum', () => {
    const columns = ONE_GROUP().columns
    const input: ReportChartInput = { ...INPUT, kind: 'bar', series: null, valueMin: -3, valueMax: null }

    const restored = fromChartInput(input, columns)

    expect(restored && toChartInput(restored, columns)).toEqual(input)
  })

  it('has no draft for a null input', () => {
    expect(fromChartInput(null, ONE_GROUP().columns)).toBeNull()
  })

  it('leaves out references whose index is outside the columns', () => {
    const restored = fromChartInput({ ...INPUT, category: 9, series: 8, values: [1, 7] }, TWO_GROUPS().columns)

    expect(restored).toMatchObject({ categoryUid: null, seriesUid: null, valueUids: [2] })
  })
})

describe('toChartInput for incomplete drafts (AC17)', () => {
  it('sends null for missing references instead of an out of range index', () => {
    const input = toChartInput(draft({ categoryUid: null, seriesUid: 99, valueUids: [2] }), ONE_GROUP().columns)

    expect(input).toMatchObject({ category: null, series: null, values: [1] })
  })

  it('sends numbers for numeric text, null for blank and the raw text for bad numbers', () => {
    const columns = ONE_GROUP().columns

    expect(toChartInput(draft({ valueMin: '12.5', valueMax: '' }), columns)).toMatchObject({ valueMin: 12.5, valueMax: null })
    expect(toChartInput(draft({ valueMin: 'abc', valueMax: 'Infinity' }), columns)).toMatchObject({ valueMin: 'abc', valueMax: 'Infinity' })
  })

  it('sends the texts and flags as they are', () => {
    const input = toChartInput(draft({ title: ' 제목 ', legend: 'none', dataLabels: true, categoryAxisTitle: 'x', valueAxisTitle: 'y' }), ONE_GROUP().columns)

    expect(input).toMatchObject({ kind: 'bar', swap: false, title: ' 제목 ', legend: 'none', dataLabels: true, categoryAxisTitle: 'x', valueAxisTitle: 'y', secondaryAxis: false })
  })
})

describe('chartDraftIssues (AC17)', () => {
  const messages = (d: ChartDraft, state: DesignerState) => chartDraftIssues(d, state.columns).map((i) => i.message)

  it('is empty for a complete draft', () => {
    expect(chartDraftIssues(draft(), ONE_GROUP().columns)).toEqual([])
  })

  it('asks for a category column', () => {
    expect(messages(draft({ categoryUid: null }), ONE_GROUP())).toContain('범주 열을 고르세요')
  })

  it('asks for the series when there are two group columns', () => {
    expect(messages(draft({ kind: 'stacked_bar', seriesUid: null, valueUids: [3] }), TWO_GROUPS())).toContain('그룹핑 컬럼이 2개면 나머지 하나를 계열로 고르세요')
  })

  it('asks for values and checks the value count of the kind', () => {
    expect(messages(draft({ valueUids: [] }), ONE_GROUP())).toContain('값 열을 고르세요')
    expect(messages(draft({ kind: 'scatter', valueUids: [2] }), ONE_GROUP())).toContain('이 차트는 값 열을 2개 골라야 합니다')
  })

  it('checks the range text and its order', () => {
    expect(messages(draft({ valueMin: 'abc' }), ONE_GROUP())).toContain('숫자를 입력하세요')
    expect(messages(draft({ valueMin: '10', valueMax: '5' }), ONE_GROUP())).toContain('최대는 최소보다 커야 합니다')
  })

  it('reports the part of the chart each issue belongs to', () => {
    const parts = chartDraftIssues(draft({ categoryUid: null, valueMin: 'abc' }), ONE_GROUP().columns).map((i) => i.part)

    expect(parts).toEqual(expect.arrayContaining(['category', 'value_min']))
  })
})

// 사용 확인: 빈 설계에서 만든 초안은 없다.
describe('empty design', () => {
  it('has no default chart', () => {
    expect(defaultChart(emptyDesign().columns, headerOf)).toBeNull()
    expect(fieldOf('deal.vendor').groupable).toBe(true)
  })
})
