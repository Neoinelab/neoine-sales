import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ReportQueryInput } from '../../shared/model/reportTypes'
import { createHttpGateway } from './index'
import { createReportsHttp } from './reports'
import { json, problem, stubFetch, stubNetworkDown } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

/** 서버 카탈로그 응답(web.md 예시 모양, 필드는 둘만). */
function serverCatalog() {
  return {
    limits: {
      columns_min: 1,
      columns_max: 30,
      conditions_max: 20,
      row_limits: [100, 1000, 10000],
      default_row_limit: 1000,
      statement_timeout_seconds: 10,
      text_value_max: 200,
      list_value_max: 100,
      last_n_days_max: 3650,
      label_max: 100,
      prefix_max: 200,
    },
    entities: [
      { key: 'deal', label: 'Deal' },
      { key: 'action', label: 'Deal Actions' },
    ],
    formats: [{ key: 'quarter', label: '분기', affects_query: true }],
    operators: [{ key: 'between', label: '범위', value: 'range' }],
    aggregates: [{ key: 'sum', label: '합계' }],
    relative_periods: [{ key: 'last_n_days', label: '최근 N일', needs_days: true }],
    fields: [
      {
        key: 'deal.amount',
        label: '금액',
        entity: 'deal',
        type: 'number',
        formats: [],
        default_format: null,
        unit: 'krw',
        operators: ['eq', 'between'],
        aggregates: ['sum', 'avg'],
        default_aggregate: 'sum',
        groupable: true,
        filterable: true,
        requires_grouping: false,
        deal_number: true,
        value_kind: null,
        options: null,
        options_source: null,
        options_category: null,
      },
      {
        key: 'deal.risk',
        label: '경고',
        entity: 'deal',
        type: 'code',
        formats: [],
        default_format: null,
        unit: null,
        operators: ['in', 'not_in', 'is_empty'],
        aggregates: ['count', 'count_distinct'],
        default_aggregate: null,
        groupable: true,
        filterable: true,
        requires_grouping: false,
        deal_number: false,
        value_kind: 'key',
        options: [{ value: 'overdue', label: '기한초과' }],
        options_source: null,
        options_category: null,
      },
    ],
  }
}

const SERVER_COLUMNS = [
  { index: 0, field: 'deal.vendor', label: 'Vendor', entity: 'deal', type: 'code', value_type: 'text', format: null, unit: null, prefix_length: null, group: true, aggregate: null },
  { index: 1, field: 'deal.amount', label: '금액 합계', entity: 'deal', type: 'number', value_type: 'integer', format: null, unit: 'krw', prefix_length: null, group: false, aggregate: 'sum' },
]

function serverResult(over: Record<string, unknown> = {}) {
  return {
    row_scope: 'deal',
    action_filter: 'none',
    deal_numbers_once: false,
    columns: SERVER_COLUMNS,
    rows: [
      ['Silverfort', 500_000_000],
      ['Okta', null],
    ],
    totals: [null, 500_000_000],
    total_count: 2,
    truncated: false,
    row_limit: 1000,
    sql: 'SELECT demo',
    elapsed_ms: 21,
    today: '2026-10-27',
    ...over,
  }
}

const REQUEST: ReportQueryInput = {
  columns: [{ field: 'deal.vendor', group: true }],
  conditions: [],
  combine: 'and',
  rowLimit: 1000,
}

describe('reports.fields over HTTP', () => {
  // 테스트 코드: RQ-103
  it('GET /reports/fields를 보낸다', async () => {
    // given: 카탈로그 응답을 돌려주는 서버
    const { calls } = stubFetch(json(serverCatalog()))

    // when: 카탈로그를 읽는다
    await createReportsHttp().fields()

    // then: GET /api/v1/reports/fields 요청이 간다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/reports/fields' })
  })

  // 테스트 코드: RQ-103
  it('카탈로그를 camelCase로 바꾸고 연산자 값 모양에 이름을 붙인다', async () => {
    // given: snake_case 카탈로그 응답
    stubFetch(json(serverCatalog()))

    // when: 카탈로그를 읽는다
    const catalog = await createReportsHttp().fields()

    // then: 한도·엔터티·포맷·연산자(shape)·집계·상대 기간이 camelCase다
    expect(catalog.limits).toEqual({
      columnsMin: 1,
      columnsMax: 30,
      conditionsMax: 20,
      rowLimits: [100, 1000, 10000],
      defaultRowLimit: 1000,
      statementTimeoutSeconds: 10,
      textValueMax: 200,
      listValueMax: 100,
      lastNDaysMax: 3650,
      labelMax: 100,
      prefixMax: 200,
    })
    expect(catalog.entities).toEqual([
      { key: 'deal', label: 'Deal' },
      { key: 'action', label: 'Deal Actions' },
    ])
    expect(catalog.formats).toEqual([{ key: 'quarter', label: '분기', affectsQuery: true }])
    expect(catalog.operators).toEqual([{ key: 'between', label: '범위', shape: 'range' }])
    expect(catalog.aggregates).toEqual([{ key: 'sum', label: '합계' }])
    expect(catalog.relativePeriods).toEqual([{ key: 'last_n_days', label: '최근 N일', needsDays: true }])
  })

  // 테스트 코드: RQ-103
  it('필드의 모든 속성과 코드 필드의 선택지를 옮긴다', async () => {
    // given: 금액 필드와 경고 필드가 든 카탈로그 응답
    stubFetch(json(serverCatalog()))

    // when: 카탈로그를 읽는다
    const { fields } = await createReportsHttp().fields()

    // then: 필드 속성이 camelCase로 모두 옮겨지고 코드 필드는 선택지를 가진다
    expect(fields[0]).toEqual({
      key: 'deal.amount',
      label: '금액',
      entity: 'deal',
      type: 'number',
      formats: [],
      defaultFormat: null,
      unit: 'krw',
      operators: ['eq', 'between'],
      aggregates: ['sum', 'avg'],
      defaultAggregate: 'sum',
      groupable: true,
      filterable: true,
      requiresGrouping: false,
      dealNumber: true,
      valueKind: null,
      options: null,
      optionsSource: null,
      optionsCategory: null,
    })
    expect(fields[1]).toMatchObject({ valueKind: 'key', options: [{ value: 'overdue', label: '기한초과' }], defaultAggregate: null })
  })

  it('HTTP 게이트웨이에 reports로 연결되어 있다', () => {
    // when: 값을 읽는다
    const actual = typeof createHttpGateway().reports.fields
    const actual2 = typeof createHttpGateway().reports.query
    // then: reports.fields와 reports.query가 함수다
    expect(actual).toBe('function')
    expect(actual2).toBe('function')
  })

  // 테스트 코드: RQ-104
  it('401을 unauthorized ApiError로 바꾼다', async () => {
    // given: 401 unauthenticated 응답
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    // when·then: 카탈로그를 읽으면 status 401, kind unauthorized로 거절된다
    await expect(createReportsHttp().fields()).rejects.toMatchObject({ status: 401, kind: 'unauthorized' })
  })
})

describe('reports.query over HTTP', () => {
  // 테스트 코드: RQ-103
  it('POST /reports/query로 설계를 snake_case로 보낸다', async () => {
    // given: 조회 결과를 돌려주는 서버, 앞 N자·표시 이름·집계·정렬이 있는 컬럼과 조건이 든 설계
    const { calls } = stubFetch(json(serverResult()))
    const input: ReportQueryInput = {
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.name', prefixLength: 5, group: false, label: '이름 앞부분', aggregate: 'count', sort: 'desc' },
      ],
      conditions: [
        { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
        { field: 'deal.expected_close', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
      ],
      combine: 'or',
      rowLimit: 10000,
    }

    // when: 조회한다
    await createReportsHttp().query(input)

    // then: POST /api/v1/reports/query이고 본문이 snake_case(prefix_length, row_limit)다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/reports/query' })
    expect(calls[0]?.body).toEqual({
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.name', prefix_length: 5, group: false, label: '이름 앞부분', aggregate: 'count', sort: 'desc' },
      ],
      conditions: [
        { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
        { field: 'deal.expected_close', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
      ],
      combine: 'or',
      row_limit: 10000,
    })
  })

  // 테스트 코드: RQ-103
  it('설계가 비운 키는 보내지 않는다', async () => {
    // given: 조회 결과를 돌려주는 서버
    const { calls } = stubFetch(json(serverResult()))

    // when: 포맷·정렬·집계·값이 없는 설계를 조회한다
    await createReportsHttp().query({
      columns: [{ field: 'deal.code', group: false }],
      conditions: [{ field: 'deal.name', operator: 'is_empty' }],
      combine: 'and',
      rowLimit: 100,
    })

    // then: 본문에 최상위 네 키만 있고 컬럼에는 field·group만, 조건에는 field·operator만 있다
    const body = calls[0]?.body as { columns: object[]; conditions: object[] } & Record<string, unknown>
    expect(Object.keys(body).sort()).toEqual(['columns', 'combine', 'conditions', 'row_limit'])
    expect(Object.keys(body.columns[0] ?? {}).sort()).toEqual(['field', 'group'])
    expect('sort' in (body.columns[0] ?? {})).toBe(false)
    expect(Object.keys(body.conditions[0] ?? {}).sort()).toEqual(['field', 'operator'])
  })

  // 테스트 코드: RQ-103
  it('결과를 camelCase로 바꾼다', async () => {
    // given: Action 행 범위의 잘린 결과 응답
    stubFetch(json(serverResult({ row_scope: 'action', action_filter: 'join', deal_numbers_once: true, truncated: true, total_count: 12_345 })))

    // when: 조회한다
    const result = await createReportsHttp().query(REQUEST)

    // then: 범위·건수·SQL·시각이 camelCase이고 행·합계 행·열이 옮겨진다
    expect(result).toMatchObject({
      rowScope: 'action',
      actionFilter: 'join',
      dealNumbersOnce: true,
      totalCount: 12_345,
      truncated: true,
      rowLimit: 1000,
      sql: 'SELECT demo',
      elapsedMs: 21,
      today: '2026-10-27',
    })
    expect(result.rows).toEqual([
      ['Silverfort', 500_000_000],
      ['Okta', null],
    ])
    expect(result.totals).toEqual([null, 500_000_000])
    expect(result.columns[1]).toEqual({
      index: 1,
      field: 'deal.amount',
      label: '금액 합계',
      entity: 'deal',
      type: 'number',
      valueType: 'integer',
      format: null,
      unit: 'krw',
      prefixLength: null,
      group: false,
      aggregate: 'sum',
    })
  })

  // 테스트 코드: RQ-103
  it('결과 열의 단위를 옮기고 다른 열은 null로 둔다', async () => {
    // given: 금액 열이 단위 krw인 결과 응답
    stubFetch(json(serverResult()))

    // when: 조회한다
    const result = await createReportsHttp().query(REQUEST)

    // then: 단위는 [null, krw]다
    expect(result.columns.map((c) => c.unit)).toEqual([null, 'krw'])
  })

  // 테스트 코드: RQ-103
  it('결과 열의 null 포맷과 앞 N자를 유지한다', async () => {
    // given: 포맷이 null인 결과 응답
    stubFetch(json(serverResult()))

    // when: 조회한다
    const result = await createReportsHttp().query(REQUEST)

    // then: 포맷 null, 앞 N자 null이다
    expect(result.columns[0]).toMatchObject({ field: 'deal.vendor', format: null, prefixLength: null })
  })

  // 테스트 코드: RQ-103
  it('어떤 형식의 열이든 앞 N자를 옮긴다', async () => {
    // given: 첫 열에 앞 N자 4가 있는 결과 응답
    const columns = [{ ...SERVER_COLUMNS[0], prefix_length: 4 }, SERVER_COLUMNS[1]]
    stubFetch(json(serverResult({ columns })))

    // when: 조회한다
    const result = await createReportsHttp().query(REQUEST)

    // then: 앞 N자가 4다
    expect(result.columns[0]?.prefixLength).toBe(4)
  })

  // 테스트 코드: RQ-103
  it('포맷 없는 카탈로그 필드는 빈 목록과 null 기본값으로 옮긴다', async () => {
    // given: 포맷 없는 경고 필드가 든 카탈로그 응답
    const catalog = serverCatalog()
    stubFetch(json(catalog))

    // when: 카탈로그를 읽는다
    const mapped = await createReportsHttp().fields()

    // then: 포맷 [], 기본 포맷 null, 단위 null이다
    const risk = mapped.fields.find((f) => f.key === 'deal.risk')
    expect(risk).toMatchObject({ formats: [], defaultFormat: null, unit: null })
  })

  // 테스트 코드: RQ-103
  it('설계에 포맷이 있을 때만 포맷을 보낸다', async () => {
    // given: 조회 결과를 돌려주는 서버
    const { calls } = stubFetch(json(serverResult()))

    // when: 포맷이 있는 컬럼과 없는 컬럼을 조회한다
    await createReportsHttp().query({
      columns: [{ field: 'deal.expected_close', format: 'quarter', group: false }, { field: 'deal.name', group: false }],
      conditions: [],
      combine: 'and',
      rowLimit: 100,
    })

    // then: 첫 컬럼에만 format이 있다
    const body = calls[0]?.body as { columns: Record<string, unknown>[] }
    expect(body.columns[0]).toEqual({ field: 'deal.expected_close', format: 'quarter', group: false })
    expect('format' in (body.columns[1] ?? {})).toBe(false)
  })

  // 테스트 코드: RQ-103
  it('그룹핑이 없으면 합계 행 null을 유지한다', async () => {
    // given: 합계 행이 null인 결과 응답
    stubFetch(json(serverResult({ totals: null })))

    // when: 조회한다
    const result = await createReportsHttp().query(REQUEST)

    // then: 합계 행이 null이다
    expect(result.totals).toBeNull()
  })

  // 테스트 코드: RQ-104
  it.each([
    ['a row shorter than the columns', { rows: [['Silverfort']] }],
    ['a row longer than the columns', { rows: [['Silverfort', 1, 2]] }],
    ['a totals row of another width', { totals: [null] }],
    ['a boolean cell', { rows: [['Silverfort', true]] }],
    ['an object cell', { rows: [['Silverfort', { a: 1 }]] }],
  ])('%s는 잘못된 응답으로 거절한다', async (_name, over) => {
    // given: 모양이 맞지 않는 결과 응답 (매개변수)
    stubFetch(json(serverResult(over)))

    // when·then: 조회하면 status 502, kind malformed-response로 거절된다
    await expect(createReportsHttp().query(REQUEST)).rejects.toMatchObject({ status: 502, kind: 'malformed-response' })
  })

  // 테스트 코드: RQ-104
  it('invalid-report 문제를 TypeError 없이 reportErrors로 옮긴다', async () => {
    // given: 위반 둘이 든 422 invalid-report 응답
    const errors = [
      { location: ['columns', 1, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: deal.nope' },
      { location: ['row_limit'], code: 'row-limit-invalid', message: '행 수 제한은 100, 1000, 10000 중 하나여야 합니다' },
    ]
    stubFetch(problem(422, 'invalid-report', '허용되지 않은 필드입니다: deal.nope', { errors }))

    // when: 조회한다
    const failure = createReportsHttp().query(REQUEST)

    // then: 상태 422·kind invalid-report·첫 위반 문구·reportErrors가 그대로다
    await expect(failure).rejects.toMatchObject({ status: 422, kind: 'invalid-report' })
    await expect(failure).rejects.toMatchObject({ message: '허용되지 않은 필드입니다: deal.nope' })
    await expect(failure).rejects.toMatchObject({ problem: { reportErrors: errors } })
  })

  // 테스트 코드: RQ-104
  it('요청 모양 오류(request-validation)는 필드 문구가 든 validation 오류로 둔다', async () => {
    // given: 필수 필드가 빠졌다는 422 request-validation 응답
    stubFetch(
      problem(422, 'request-validation', '요청 형식이 올바르지 않습니다', {
        errors: [{ loc: ['body', 'columns', 0, 'field'], msg: 'Field required', type: 'missing' }],
      }),
    )

    // when·then: 조회하면 kind validation에 필드 위치와 문구가 든 메시지로 거절된다
    await expect(createReportsHttp().query(REQUEST)).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '요청 형식이 올바르지 않습니다 — columns.0.field: Field required',
    })
  })

  // 테스트 코드: RQ-104
  it('시간 초과는 서버 문구를 유지한다', async () => {
    // given: 503 report-timeout 응답
    const detail = '조회가 10초 안에 끝나지 않았습니다. 조건을 좁히거나 컬럼을 줄이세요'
    stubFetch(problem(503, 'report-timeout', detail))

    // when·then: 조회하면 status 503, kind report-timeout, 서버 문구로 거절된다
    await expect(createReportsHttp().query(REQUEST)).rejects.toMatchObject({ status: 503, kind: 'report-timeout', message: detail })
  })

  // 테스트 코드: RQ-104
  it('연결 끊김은 network 오류로 바꾼다', async () => {
    // given: 서버에 연결할 수 없는 상태
    stubNetworkDown()

    // when·then: 조회하면 status 0, kind network, 연결 문구로 거절된다
    await expect(createReportsHttp().query(REQUEST)).rejects.toMatchObject({
      status: 0,
      kind: 'network',
      message: '서버에 연결할 수 없습니다.',
    })
  })
})
