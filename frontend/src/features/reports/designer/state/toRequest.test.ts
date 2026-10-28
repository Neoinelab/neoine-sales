import { describe, expect, it } from 'vitest'
import type { ConditionDraft, DesignerState } from './designerState'
import type { ReportOperator } from '../../../../shared/model/reportTypes'
import { conditionUidAt, fieldOf, reduce, REPORT_CATALOG, uidAt, withColumns } from '../../../../test/reportDesigner'
import { toReportRequest } from './toRequest'

/** 조건 하나를 추가하고 연산자·초안을 지정한 설계. */
function withCondition(state: DesignerState, fieldKey: string, operator: ReportOperator, draft: ConditionDraft): DesignerState {
  const added = reduce(state, { type: 'addCondition', field: fieldOf(fieldKey) })
  const uid = conditionUidAt(added, added.conditions.length - 1)
  return reduce(added, { type: 'changeOperator', uid, operator }, { type: 'changeDraft', uid, draft })
}

function build(state: DesignerState) {
  const result = toReportRequest(state, REPORT_CATALOG)
  if (!('request' in result)) throw new Error(`요청을 만들지 못함: ${JSON.stringify(result)}`)
  return result
}

function issuesOf(state: DesignerState) {
  const result = toReportRequest(state, REPORT_CATALOG)
  if (!('inputIssues' in result)) throw new Error('요청이 만들어짐')
  return result.inputIssues
}

/** 컬럼 하나와 조건 하나만 있는 설계의 조건 값. */
function conditionValue(fieldKey: string, operator: ReportOperator, draft: ConditionDraft): unknown {
  const state = withCondition(withColumns('deal.code'), fieldKey, operator, draft)
  return build(state).request.conditions[0]
}

describe('toReportRequest column rules (AC11)', () => {
  it('builds the vendor by quarter request of the design example', () => {
    let state = withColumns('deal.vendor', 'deal.expected_close', 'deal.amount')
    state = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } },
      { type: 'updateColumn', uid: uidAt(state, 1), patch: { group: true, format: 'quarter' } },
      { type: 'updateColumn', uid: uidAt(state, 2), patch: { label: '금액 합계' } },
    )
    state = withCondition(state, 'deal.vendor', 'in', { shape: 'list', values: ['6', '1'] })
    state = withCondition(state, 'deal.amount', 'gte', { shape: 'number', text: '1,500' })
    state = reduce(state, { type: 'setSort', sort: { uid: uidAt(state, 2), direction: 'desc' } })

    const { request, columnUids, conditionUids } = build(state)

    expect(request).toEqual({
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.expected_close', format: 'quarter', group: true },
        { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum', label: '금액 합계' },
      ],
      conditions: [
        { field: 'deal.vendor', operator: 'in', value: [6, 1] },
        { field: 'deal.amount', operator: 'gte', value: 1_500_000 },
      ],
      combine: 'and',
      sort: { column: 2, direction: 'desc' },
      rowLimit: 1000,
    })
    expect(columnUids).toEqual(state.columns.map((c) => c.uid))
    expect(conditionUids).toEqual(state.conditions.map((c) => c.uid))
  })

  it('sends combine and row limit as designed and leaves the sort out when there is none', () => {
    const state = reduce(withColumns('deal.code'), { type: 'setCombine', combine: 'or' }, { type: 'setRowLimit', rowLimit: 10000 })

    const { request } = build(state)

    expect(request).toMatchObject({ combine: 'or', rowLimit: 10000, conditions: [] })
    expect('sort' in request).toBe(false)
  })

  it('omits label when blank or equal to the field name', () => {
    let state = withColumns('deal.name', 'deal.name', 'deal.name', 'deal.name')
    state = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { label: '   ' } },
      { type: 'updateColumn', uid: uidAt(state, 1), patch: { label: ' Deal 이름 ' } },
      { type: 'updateColumn', uid: uidAt(state, 2), patch: { label: '  이름 앞부분  ', prefixOn: true, prefixLength: 7 } },
    )

    const { columns } = build(state).request

    expect(columns[0]).toEqual({ field: 'deal.name', group: false })
    expect(columns[1]).toEqual({ field: 'deal.name', group: false })
    expect(columns[2]).toEqual({ field: 'deal.name', prefixLength: 7, group: false, label: '이름 앞부분' })
    expect(columns[3]).toEqual({ field: 'deal.name', group: false })
  })

  it('sends the aggregate only when the column has one', () => {
    let state = withColumns('deal.vendor', 'deal.status_days', 'deal.name')
    state = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    const { columns } = build(state).request

    expect(columns.map((c) => c.aggregate)).toEqual([undefined, 'avg', undefined])
    expect('aggregate' in (columns[0] ?? {})).toBe(false)
  })
})

describe('toReportRequest prefix option (AC14, AC15)', () => {
  const on = (state: DesignerState, index: number, prefixLength: number | null) =>
    reduce(state, { type: 'updateColumn', uid: uidAt(state, index), patch: { prefixOn: true, prefixLength } })

  it('sends no format key for a field without formats', () => {
    const { columns } = build(withColumns('deal.name', 'deal.status', 'deal.owner')).request

    for (const column of columns) expect('format' in column).toBe(false)
  })

  it('sends the format of a number field and the prefix length together', () => {
    const { columns } = build(on(withColumns('deal.amount'), 0, 5)).request

    expect(columns[0]).toEqual({ field: 'deal.amount', format: 'krw_thousand', prefixLength: 5, group: false })
  })

  it('sends the prefix length only while the option is on', () => {
    const state = on(withColumns('deal.name'), 0, 5)
    const off = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { prefixOn: false } })

    expect(build(state).request.columns[0]).toMatchObject({ prefixLength: 5 })
    expect('prefixLength' in (build(off).request.columns[0] ?? {})).toBe(false)
  })

  it.each([
    ['empty', null],
    ['zero', 0],
    ['above the limit', 201],
    ['fractional', 1.5],
  ])('makes no request and points at the column when N is %s', (_name, value) => {
    const state = on(withColumns('deal.code', 'deal.name'), 1, value)

    const result = toReportRequest(state, REPORT_CATALOG)

    expect('request' in result).toBe(false)
    expect(issuesOf(state)).toEqual([{ uid: uidAt(state, 1), part: 'prefix_length', message: '1~200 사이 정수를 입력하세요' }])
  })

  it.each([1, 200])('accepts N=%i at the limits', (value) => {
    const { columns } = build(on(withColumns('deal.name'), 0, value)).request

    expect(columns[0]).toMatchObject({ prefixLength: value })
  })
})

describe('toReportRequest condition values (AC11)', () => {
  it('converts thousand won to won for amount conditions', () => {
    expect(conditionValue('deal.amount', 'eq', { shape: 'number', text: '1,500' })).toEqual({ field: 'deal.amount', operator: 'eq', value: 1_500_000 })
    expect(conditionValue('deal.amount', 'between', { shape: 'range', low: '1,000', high: '2,000' })).toEqual({
      field: 'deal.amount',
      operator: 'between',
      value: [1_000_000, 2_000_000],
    })
    expect(conditionValue('deal.amount', 'lt', { shape: 'number', text: '0' })).toMatchObject({ value: 0 })
    expect(conditionValue('deal.amount', 'gt', { shape: 'number', text: '-5' })).toMatchObject({ value: -5000 })
  })

  it('does not multiply other numbers', () => {
    expect(conditionValue('deal.users', 'gte', { shape: 'number', text: '1,500' })).toMatchObject({ value: 1500 })
    expect(conditionValue('deal.status_days', 'between', { shape: 'range', low: '3', high: '9' })).toMatchObject({ value: [3, 9] })
  })

  it('sends ids as integers and keys as strings', () => {
    expect(conditionValue('deal.vendor', 'in', { shape: 'list', values: ['6', '1'] })).toMatchObject({ value: [6, 1] })
    expect(conditionValue('deal.owner', 'not_in', { shape: 'list', values: ['2'] })).toMatchObject({ value: [2] })
    expect(conditionValue('action.type', 'in', { shape: 'list', values: ['3'] })).toMatchObject({ value: [3] })
    expect(conditionValue('deal.bant_budget', 'in', { shape: 'list', values: ['4'] })).toMatchObject({ value: [4] })
    expect(conditionValue('deal.status', 'in', { shape: 'list', values: ['prospecting', 'introduction'] })).toMatchObject({
      value: ['prospecting', 'introduction'],
    })
    expect(conditionValue('deal.quote_submitted', 'in', { shape: 'list', values: ['YES'] })).toMatchObject({ value: ['YES'] })
  })

  it('trims text and sends no value for operators without one', () => {
    expect(conditionValue('deal.name', 'contains', { shape: 'text', text: '  은행 ' })).toEqual({ field: 'deal.name', operator: 'contains', value: '은행' })
    const empty = conditionValue('deal.name', 'is_empty', { shape: 'none' })
    expect(empty).toEqual({ field: 'deal.name', operator: 'is_empty' })
    expect('value' in (empty as object)).toBe(false)
  })

  it('sends dates and date ranges as YYYY-MM-DD', () => {
    expect(conditionValue('deal.expected_close', 'before', { shape: 'date', day: '2026-10-27' })).toMatchObject({ value: '2026-10-27' })
    expect(conditionValue('deal.created_at', 'between', { shape: 'date_range', first: '2026-01-01', last: '2026-03-31' })).toMatchObject({
      value: ['2026-01-01', '2026-03-31'],
    })
  })

  it('sends relative periods with days only for last n days', () => {
    expect(conditionValue('deal.expected_close', 'relative', { shape: 'relative', period: 'this_year', days: '30' })).toMatchObject({
      value: { period: 'this_year' },
    })
    const value = (conditionValue('deal.expected_close', 'relative', { shape: 'relative', period: 'last_n_days', days: '30' }) as { value: object }).value
    expect(value).toEqual({ period: 'last_n_days', days: 30 })
    const noDays = (conditionValue('deal.expected_close', 'relative', { shape: 'relative', period: 'this_month', days: '' }) as { value: object }).value
    expect('days' in noDays).toBe(false)
  })
})

describe('toReportRequest unreadable inputs (AC11)', () => {
  const cases: [string, string, ReportOperator, ConditionDraft, string, RegExp | string][] = [
    ['text is empty', 'deal.name', 'contains', { shape: 'text', text: '   ' }, 'value', '값을 입력하세요'],
    ['list is empty', 'deal.vendor', 'in', { shape: 'list', values: [] }, 'value', '하나 이상 선택하세요'],
    ['number has a decimal point', 'deal.users', 'eq', { shape: 'number', text: '1.5' }, 'value', /정수/],
    ['number is a word', 'deal.users', 'eq', { shape: 'number', text: 'abc' }, 'value', /정수/],
    ['number is empty', 'deal.users', 'eq', { shape: 'number', text: '' }, 'value', /정수/],
    ['amount has a decimal point', 'deal.amount', 'eq', { shape: 'number', text: '1.5' }, 'value', '천원 단위 정수로 입력하세요'],
    ['amount is too large', 'deal.amount', 'eq', { shape: 'number', text: '9,007,199,254,741' }, 'value', '천원 단위 정수로 입력하세요'],
    ['range low is a word', 'deal.users', 'between', { shape: 'range', low: 'x', high: '5' }, 'low', /정수/],
    ['range high is empty', 'deal.users', 'between', { shape: 'range', low: '1', high: '' }, 'high', /정수/],
    ['date is empty', 'deal.expected_close', 'after', { shape: 'date', day: '' }, 'day', '날짜를 고르세요'],
    ['date range start is empty', 'deal.expected_close', 'between', { shape: 'date_range', first: '', last: '2026-12-31' }, 'first', '날짜를 고르세요'],
    ['date range end is empty', 'deal.expected_close', 'between', { shape: 'date_range', first: '2026-01-01', last: '' }, 'last', '날짜를 고르세요'],
    ['days is zero', 'deal.expected_close', 'relative', { shape: 'relative', period: 'last_n_days', days: '0' }, 'days', '1~3650 사이 정수를 입력하세요'],
    ['days is above the limit', 'deal.expected_close', 'relative', { shape: 'relative', period: 'last_n_days', days: '3651' }, 'days', '1~3650 사이 정수를 입력하세요'],
    ['days is empty', 'deal.expected_close', 'relative', { shape: 'relative', period: 'last_n_days', days: '' }, 'days', '1~3650 사이 정수를 입력하세요'],
  ]

  it.each(cases)('reports unreadable inputs without building a request: %s', (_name, fieldKey, operator, draft, part, message) => {
    const state = withCondition(withColumns('deal.code'), fieldKey, operator, draft)

    const issues = issuesOf(state)

    expect(issues).toHaveLength(1)
    expect(issues[0]).toMatchObject({ uid: conditionUidAt(state, 0), part })
    if (typeof message === 'string') expect(issues[0]?.message).toBe(message)
    else expect(issues[0]?.message).toMatch(message)
  })

  it('reports that the start of a range is after the end', () => {
    const state = withCondition(withColumns('deal.code'), 'deal.users', 'between', { shape: 'range', low: '9', high: '3' })

    const issues = issuesOf(state)

    expect(issues).toHaveLength(1)
    expect(issues[0]?.message).toBe('시작이 끝보다 클 수 없습니다')
    expect(['low', 'high']).toContain(issues[0]?.part)
  })

  it('reports every unreadable condition at once', () => {
    let state = withCondition(withColumns('deal.code'), 'deal.name', 'contains', { shape: 'text', text: '' })
    state = withCondition(state, 'deal.users', 'eq', { shape: 'number', text: 'x' })

    const issues = issuesOf(state)

    expect(issues.map((i) => i.uid)).toEqual([conditionUidAt(state, 0), conditionUidAt(state, 1)])
  })
})
