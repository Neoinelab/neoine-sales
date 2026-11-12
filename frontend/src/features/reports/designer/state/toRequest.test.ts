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

describe('toReportRequest column rules', () => {
  // 테스트 코드: RQ-086
  it('Vendor×분기 설계 예시를 요청으로 만든다', () => {
    // given: Vendor·분기 그룹, 금액 내림차순 정렬(표시 이름), Vendor·금액 조건을 설계했다
    let state = withColumns('deal.vendor', 'deal.expected_close', 'deal.amount')
    state = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } },
      { type: 'updateColumn', uid: uidAt(state, 1), patch: { group: true, format: 'quarter' } },
      { type: 'updateColumn', uid: uidAt(state, 2), patch: { label: '금액 합계', sort: 'desc' } },
    )
    state = withCondition(state, 'deal.vendor', 'in', { shape: 'list', values: ['6', '1'] })
    state = withCondition(state, 'deal.amount', 'gte', { shape: 'number', text: '1,500,000' })

    // when: 설계를 요청으로 바꾼다
    const { request, columnUids, conditionUids } = build(state)

    // then: 컬럼·조건·결합·행 수가 설계 그대로이고 uid 목록도 설계와 같다
    expect(request).toEqual({
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.expected_close', format: 'quarter', group: true },
        { field: 'deal.amount', group: false, aggregate: 'sum', label: '금액 합계', sort: 'desc' },
      ],
      conditions: [
        { field: 'deal.vendor', operator: 'in', value: [6, 1] },
        { field: 'deal.amount', operator: 'gte', value: 1_500_000 },
      ],
      combine: 'and',
      rowLimit: 1000,
    })
    expect(columnUids).toEqual(state.columns.map((c) => c.uid))
    expect(conditionUids).toEqual(state.conditions.map((c) => c.uid))
  })

  // 테스트 코드: RQ-086
  it('결합과 행 수 제한을 설계대로 보내고 최상위 sort는 없다', () => {
    // given: 결합 or, 행 수 10000으로 설계했다
    const state = reduce(withColumns('deal.code'), { type: 'setCombine', combine: 'or' }, { type: 'setRowLimit', rowLimit: 10000 })

    // when: 설계를 요청으로 바꾼다
    const { request } = build(state)

    // then: 결합·행 수가 설계대로이고 최상위 sort가 없다
    expect(request).toMatchObject({ combine: 'or', rowLimit: 10000, conditions: [] })
    expect('sort' in request).toBe(false)
  })

  // 테스트 코드: RQ-086
  it('표시 이름이 비었거나 필드 이름과 같으면 보내지 않는다', () => {
    // given: 표시 이름이 공백, 필드 이름과 같음, 다른 이름(앞 N자 7), 없음인 컬럼 넷
    let state = withColumns('deal.name', 'deal.name', 'deal.name', 'deal.name')
    state = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { label: '   ' } },
      { type: 'updateColumn', uid: uidAt(state, 1), patch: { label: ' Deal 이름 ' } },
      { type: 'updateColumn', uid: uidAt(state, 2), patch: { label: '  이름 앞부분  ', prefixOn: true, prefixLength: 7 } },
    )

    // when: 설계를 요청으로 바꾼다
    const { columns } = build(state).request

    // then: 공백·같은 이름·없음은 label 없이, 다른 이름은 다듬어 보낸다
    expect(columns[0]).toEqual({ field: 'deal.name', group: false })
    expect(columns[1]).toEqual({ field: 'deal.name', group: false })
    expect(columns[2]).toEqual({ field: 'deal.name', prefixLength: 7, group: false, label: '이름 앞부분' })
    expect(columns[3]).toEqual({ field: 'deal.name', group: false })
  })

  // 테스트 코드: RQ-086
  it('집계가 있는 컬럼만 집계를 보낸다', () => {
    // given: Vendor를 그룹핑한 설계
    let state = withColumns('deal.vendor', 'deal.status_days', 'deal.name')
    state = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { group: true } })

    // when: 설계를 요청으로 바꾼다
    const { columns } = build(state).request

    // then: 그룹 컬럼은 집계 키가 없고 나머지는 평균·건수다
    expect(columns.map((c) => c.aggregate)).toEqual([undefined, 'avg', 'count'])
    expect('aggregate' in (columns[0] ?? {})).toBe(false)
  })
})

describe('toReportRequest prefix option', () => {
  const on = (state: DesignerState, index: number, prefixLength: number | null) =>
    reduce(state, { type: 'updateColumn', uid: uidAt(state, index), patch: { prefixOn: true, prefixLength } })

  // 테스트 코드: RQ-086
  it('포맷 없는 필드는 숫자도 포맷 키를 보내지 않는다', () => {
    // when: 텍스트·코드·사용자·숫자 컬럼을 요청으로 바꾼다
    const { columns } = build(withColumns('deal.name', 'deal.status', 'deal.owner', 'deal.amount', 'deal.users')).request

    // then: 어느 컬럼에도 format 키가 없다
    for (const column of columns) expect('format' in column).toBe(false)
  })

  // 테스트 코드: RQ-086
  it('숫자 필드의 앞 N자는 포맷 키 없이 보낸다', () => {
    // when: 앞 N자 5를 켠 금액 컬럼을 요청으로 바꾼다
    const { columns } = build(on(withColumns('deal.amount'), 0, 5)).request

    // then: 앞 N자 5만 있고 포맷 키는 없다
    expect(columns[0]).toEqual({ field: 'deal.amount', prefixLength: 5, group: false })
  })

  // 테스트 코드: RQ-086
  it('앞 N자는 옵션이 켜져 있는 동안만 보낸다', () => {
    // given: 앞 N자 5를 켠 설계와 끈 설계
    const state = on(withColumns('deal.name'), 0, 5)
    const off = reduce(state, { type: 'updateColumn', uid: uidAt(state, 0), patch: { prefixOn: false } })

    // when: 앞 N자를 켠 설계와 끈 설계로 요청을 만든다
    const actual = build(state).request.columns[0]
    const actual2 = 'prefixLength' in (build(off).request.columns[0] ?? {})
    // then: 켠 설계는 앞 N자 5를 보내고 끈 설계는 키가 없다
    expect(actual).toMatchObject({ prefixLength: 5 })
    expect(actual2).toBe(false)
  })

  // 테스트 코드: RQ-077
  it.each([
    ['empty', null],
    ['zero', 0],
    ['above the limit', 201],
    ['fractional', 1.5],
  ])('N이 %s이면 요청을 만들지 않고 그 컬럼을 가리킨다', (_name, value) => {
    // given: 둘째 컬럼에 잘못된 N (매개변수)
    const state = on(withColumns('deal.code', 'deal.name'), 1, value)

    // when: 설계를 요청으로 바꾼다
    const result = toReportRequest(state, REPORT_CATALOG)

    // then: 요청이 없고 그 컬럼의 앞 N자에 안내가 붙는다
    expect('request' in result).toBe(false)
    expect(issuesOf(state)).toEqual([{ uid: uidAt(state, 1), part: 'prefix_length', message: '1~200 사이 정수를 입력하세요' }])
  })

  // 테스트 코드: RQ-077
  it.each([1, 200])('N=%i 한도 값을 받아들인다', (value) => {
    // when: 한도 값 N의 설계를 요청으로 바꾼다 (전제: 1과 200 매개변수)
    const { columns } = build(on(withColumns('deal.name'), 0, value)).request

    // then: 앞 N자가 그 값이다
    expect(columns[0]).toMatchObject({ prefixLength: value })
  })
})

describe('toReportRequest condition values', () => {
  // 테스트 코드: RQ-082
  it('금액 조건은 입력한 원을 곱하지 않고 보낸다', () => {
    // when: 금액 조건의 같음 1,000,000과 범위 1,000,000~5,000,000 값을 만든다
    const actual = conditionValue('deal.amount', 'eq', { shape: 'number', text: '1,000,000' })
    const actual2 = conditionValue('deal.amount', 'between', { shape: 'range', low: '1,000,000', high: '5,000,000' })
    const actual3 = conditionValue('deal.amount', 'lt', { shape: 'number', text: '0' })
    const actual4 = conditionValue('deal.amount', 'gt', { shape: 'number', text: '-5' })
    // then: 같음·범위·0·음수 입력이 입력한 원 그대로의 값이다
    expect(actual).toEqual({ field: 'deal.amount', operator: 'eq', value: 1_000_000 })
    expect(actual2).toEqual({
      field: 'deal.amount',
      operator: 'between',
      value: [1_000_000, 5_000_000],
    })
    expect(actual3).toMatchObject({ value: 0 })
    expect(actual4).toMatchObject({ value: -5 })
  })

  // 테스트 코드: RQ-082
  it('금액은 안전 정수 한도까지 받아들인다', () => {
    // when: 금액 조건에 9,007,199,254,740,991을 넣어 값을 만든다
    const actual = conditionValue('deal.amount', 'eq', { shape: 'number', text: '9,007,199,254,740,991' })
    // then: 9,007,199,254,740,991이 최대 안전 정수 값으로 만들어진다
    expect(actual).toMatchObject({ value: Number.MAX_SAFE_INTEGER })
  })

  // 테스트 코드: RQ-082
  it('다른 숫자 필드도 곱하지 않는다', () => {
    // when: 사용자 수 1,500 이상과 경과일 3~9 범위의 조건 값을 만든다
    const actual = conditionValue('deal.users', 'gte', { shape: 'number', text: '1,500' })
    const actual2 = conditionValue('deal.status_days', 'between', { shape: 'range', low: '3', high: '9' })
    // then: Users count와 체류 일수는 입력 그대로의 값이다
    expect(actual).toMatchObject({ value: 1500 })
    expect(actual2).toMatchObject({ value: [3, 9] })
  })

  // 테스트 코드: RQ-086
  it('id 필드는 정수로, key 필드는 문자열로 보낸다', () => {
    // when: Vendor 포함 목록과 담당자 제외 목록의 조건 값을 만든다
    const actual = conditionValue('deal.vendor', 'in', { shape: 'list', values: ['6', '1'] })
    const actual2 = conditionValue('deal.owner', 'not_in', { shape: 'list', values: ['2'] })
    const actual3 = conditionValue('action.type', 'in', { shape: 'list', values: ['3'] })
    const actual4 = conditionValue('deal.bant_budget', 'in', { shape: 'list', values: ['4'] })
    const actual5 = conditionValue('deal.status', 'in', { shape: 'list', values: ['prospecting', 'introduction'] })
    const actual6 = conditionValue('deal.quote_submitted', 'in', { shape: 'list', values: ['YES'] })
    // then: Vendor·담당자·Action 유형·BANT는 정수 목록, Status·견적 제출은 문자열 목록이다
    expect(actual).toMatchObject({ value: [6, 1] })
    expect(actual2).toMatchObject({ value: [2] })
    expect(actual3).toMatchObject({ value: [3] })
    expect(actual4).toMatchObject({ value: [4] })
    expect(actual5).toMatchObject({
      value: ['prospecting', 'introduction'],
    })
    expect(actual6).toMatchObject({ value: ['YES'] })
  })

  // 테스트 코드: RQ-086
  it('텍스트는 다듬어 보내고 값 없는 연산자는 value를 보내지 않는다', () => {
    // when: 앞뒤 공백이 있는 검색어와 비어 있음 연산자로 조건 값을 만든다
    const trimmed = conditionValue('deal.name', 'contains', { shape: 'text', text: '  은행 ' })
    const empty = conditionValue('deal.name', 'is_empty', { shape: 'none' })
    // then: 검색어는 앞뒤 공백이 지워지고 비어 있음 연산자에는 value 키가 없다
    expect(trimmed).toEqual({ field: 'deal.name', operator: 'contains', value: '은행' })
    expect(empty).toEqual({ field: 'deal.name', operator: 'is_empty' })
    expect('value' in (empty as object)).toBe(false)
  })

  // 테스트 코드: RQ-084
  it('날짜와 날짜 범위를 YYYY-MM-DD로 보낸다', () => {
    // when: 예상 종료일 이전 날짜와 생성일 기간의 조건 값을 만든다
    const actual = conditionValue('deal.expected_close', 'before', { shape: 'date', day: '2026-10-27' })
    const actual2 = conditionValue('deal.created_at', 'between', { shape: 'date_range', first: '2026-01-01', last: '2026-03-31' })
    // then: 날짜와 시각 필드의 범위가 ISO 날짜 문자열이다
    expect(actual).toMatchObject({ value: '2026-10-27' })
    expect(actual2).toMatchObject({
      value: ['2026-01-01', '2026-03-31'],
    })
  })

  // 테스트 코드: RQ-083
  it.each(['last_1_month', 'last_3_months', 'last_6_months'] as const)('%s는 일수 초안이 남아 있어도 일수 없이 보낸다', (period) => {
    // when: 일수 초안 30이 남은 채 개월 기간 조건 값을 만든다 (전제: 개월 기간 매개변수)
    const value = (conditionValue('deal.expected_close', 'relative', { shape: 'relative', period, days: '30' }) as { value: object }).value
    // then: 값에 기간만 있고 일수가 없다
    expect(value).toEqual({ period })
  })

  // 테스트 코드: RQ-083
  it('상대 기간은 최근 N일일 때만 일수를 보낸다', () => {
    // when: 올해·최근 N일·이번 달 상대 기간 조건 값을 만든다
    const thisYear = conditionValue('deal.expected_close', 'relative', { shape: 'relative', period: 'this_year', days: '30' })
    const lastDays = (conditionValue('deal.expected_close', 'relative', { shape: 'relative', period: 'last_n_days', days: '30' }) as { value: object }).value
    const noDays = (conditionValue('deal.expected_close', 'relative', { shape: 'relative', period: 'this_month', days: '' }) as { value: object }).value
    // then: 올해는 일수 없이, 최근 N일은 일수 30과 함께, 이번 달은 빈 일수에도 일수 키가 없다
    expect(thisYear).toMatchObject({ value: { period: 'this_year' } })
    expect(lastDays).toEqual({ period: 'last_n_days', days: 30 })
    expect('days' in noDays).toBe(false)
  })
})

describe('toReportRequest unreadable inputs', () => {
  const cases: [string, string, ReportOperator, ConditionDraft, string, RegExp | string][] = [
    ['text is empty', 'deal.name', 'contains', { shape: 'text', text: '   ' }, 'value', '값을 입력하세요'],
    ['list is empty', 'deal.vendor', 'in', { shape: 'list', values: [] }, 'value', '하나 이상 선택하세요'],
    ['number has a decimal point', 'deal.users', 'eq', { shape: 'number', text: '1.5' }, 'value', /정수/],
    ['number is a word', 'deal.users', 'eq', { shape: 'number', text: 'abc' }, 'value', /정수/],
    ['number is empty', 'deal.users', 'eq', { shape: 'number', text: '' }, 'value', /정수/],
    ['amount has a decimal point', 'deal.amount', 'eq', { shape: 'number', text: '1.5' }, 'value', '정수로 입력하세요'],
    ['amount is too large', 'deal.amount', 'eq', { shape: 'number', text: '9,007,199,254,740,992' }, 'value', '정수로 입력하세요'],
    ['range low is a word', 'deal.users', 'between', { shape: 'range', low: 'x', high: '5' }, 'low', /정수/],
    ['range high is empty', 'deal.users', 'between', { shape: 'range', low: '1', high: '' }, 'high', /정수/],
    ['date is empty', 'deal.expected_close', 'after', { shape: 'date', day: '' }, 'day', '날짜를 고르세요'],
    ['date range start is empty', 'deal.expected_close', 'between', { shape: 'date_range', first: '', last: '2026-12-31' }, 'first', '날짜를 고르세요'],
    ['date range end is empty', 'deal.expected_close', 'between', { shape: 'date_range', first: '2026-01-01', last: '' }, 'last', '날짜를 고르세요'],
    ['days is zero', 'deal.expected_close', 'relative', { shape: 'relative', period: 'last_n_days', days: '0' }, 'days', '1~3650 사이 정수를 입력하세요'],
    ['days is above the limit', 'deal.expected_close', 'relative', { shape: 'relative', period: 'last_n_days', days: '3651' }, 'days', '1~3650 사이 정수를 입력하세요'],
    ['days is empty', 'deal.expected_close', 'relative', { shape: 'relative', period: 'last_n_days', days: '' }, 'days', '1~3650 사이 정수를 입력하세요'],
  ]

  // 테스트 코드: RQ-085
  it.each(cases)('읽을 수 없는 입력은 요청을 만들지 않고 그 칸에 안내한다: %s', (_name, fieldKey, operator, draft, part, message) => {
    // given: 읽을 수 없는 조건 값 (매개변수)
    const state = withCondition(withColumns('deal.code'), fieldKey, operator, draft)

    // when: 설계를 요청으로 바꾼다
    const issues = issuesOf(state)

    // then: 그 조건의 해당 칸에 기대 안내가 하나 붙는다
    expect(issues).toHaveLength(1)
    expect(issues[0]).toMatchObject({ uid: conditionUidAt(state, 0), part })
    if (typeof message === 'string') expect(issues[0]?.message).toBe(message)
    else expect(issues[0]?.message).toMatch(message)
  })

  // 테스트 코드: RQ-085
  it('범위의 시작이 끝보다 크면 안내한다', () => {
    // given: 시작 9, 끝 3인 범위 조건
    const state = withCondition(withColumns('deal.code'), 'deal.users', 'between', { shape: 'range', low: '9', high: '3' })

    // when: 설계를 요청으로 바꾼다
    const issues = issuesOf(state)

    // then: 시작이 끝보다 클 수 없다는 안내 하나다
    expect(issues).toHaveLength(1)
    expect(issues[0]?.message).toBe('시작이 끝보다 클 수 없습니다')
    expect(['low', 'high']).toContain(issues[0]?.part)
  })

  // 테스트 코드: RQ-085
  it('읽을 수 없는 조건을 한꺼번에 모두 안내한다', () => {
    // given: 읽을 수 없는 조건 둘
    let state = withCondition(withColumns('deal.code'), 'deal.name', 'contains', { shape: 'text', text: '' })
    state = withCondition(state, 'deal.users', 'eq', { shape: 'number', text: 'x' })

    // when: 설계를 요청으로 바꾼다
    const issues = issuesOf(state)

    // then: 두 조건의 안내가 순서대로 있다
    expect(issues.map((i) => i.uid)).toEqual([conditionUidAt(state, 0), conditionUidAt(state, 1)])
  })
})

describe('toReportRequest column sort', () => {
  // 테스트 코드: RQ-086
  it('정렬이 있는 컬럼에만 정렬을 컬럼 순서대로 담는다', () => {
    // given: 첫째·셋째 컬럼에 정렬을 준 설계
    let state = withColumns('deal.name', 'deal.vendor', 'deal.code')
    state = reduce(
      state,
      { type: 'updateColumn', uid: uidAt(state, 0), patch: { sort: 'asc' } },
      { type: 'updateColumn', uid: uidAt(state, 2), patch: { sort: 'desc' } },
    )

    // when: 설계를 요청으로 바꾼다
    const { request } = build(state)

    // then: 정렬은 첫째 asc, 셋째 desc뿐이고 최상위 sort는 없다
    expect(request.columns.map((c) => c.sort)).toEqual(['asc', undefined, 'desc'])
    expect('sort' in (request.columns[1] ?? {})).toBe(false)
    expect('sort' in request).toBe(false)
  })
})

describe('toReportRequest money conditions', () => {
  // 테스트 코드: RQ-082
  it('금액·Users count·체류 일수 조건을 모두 입력한 값 그대로 보낸다', () => {
    // given: 금액, Users count, 체류 일수 조건
    let state = withColumns('deal.code')
    state = withCondition(state, 'deal.amount', 'gte', { shape: 'number', text: '1,500,000' })
    state = withCondition(state, 'deal.users', 'gte', { shape: 'number', text: '5' })
    state = withCondition(state, 'deal.status_days', 'lte', { shape: 'number', text: '30' })

    // when: 설계를 요청으로 바꾼다
    const { request } = build(state)

    // then: 값이 입력한 숫자 그대로다
    expect(request.conditions.map((c) => c.value)).toEqual([1_500_000, 5, 30])
  })
})
