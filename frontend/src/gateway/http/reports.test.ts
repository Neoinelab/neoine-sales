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
    formats: [{ key: 'krw_thousand', label: '천원', affects_query: false }],
    operators: [{ key: 'between', label: '범위', value: 'range' }],
    aggregates: [{ key: 'sum', label: '합계' }],
    relative_periods: [{ key: 'last_n_days', label: '최근 N일', needs_days: true }],
    fields: [
      {
        key: 'deal.amount',
        label: '금액(원)',
        entity: 'deal',
        type: 'number',
        formats: ['thousands', 'krw_thousand'],
        default_format: 'krw_thousand',
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
  { index: 0, field: 'deal.vendor', label: 'Vendor', entity: 'deal', type: 'code', value_type: 'text', format: null, prefix_length: null, group: true, aggregate: null },
  { index: 1, field: 'deal.amount', label: '금액 합계', entity: 'deal', type: 'number', value_type: 'integer', format: 'krw_thousand', prefix_length: null, group: false, aggregate: 'sum' },
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
  it('sends GET /reports/fields', async () => {
    const { calls } = stubFetch(json(serverCatalog()))

    await createReportsHttp().fields()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/reports/fields' })
  })

  it('maps the catalog to camel case and names the operator value shape', async () => {
    stubFetch(json(serverCatalog()))

    const catalog = await createReportsHttp().fields()

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
    expect(catalog.formats).toEqual([{ key: 'krw_thousand', label: '천원', affectsQuery: false }])
    expect(catalog.operators).toEqual([{ key: 'between', label: '범위', shape: 'range' }])
    expect(catalog.aggregates).toEqual([{ key: 'sum', label: '합계' }])
    expect(catalog.relativePeriods).toEqual([{ key: 'last_n_days', label: '최근 N일', needsDays: true }])
  })

  it('maps every field property including the choices of a code field', async () => {
    stubFetch(json(serverCatalog()))

    const { fields } = await createReportsHttp().fields()

    expect(fields[0]).toEqual({
      key: 'deal.amount',
      label: '금액(원)',
      entity: 'deal',
      type: 'number',
      formats: ['thousands', 'krw_thousand'],
      defaultFormat: 'krw_thousand',
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

  it('is wired into the HTTP gateway as reports', () => {
    expect(typeof createHttpGateway().reports.fields).toBe('function')
    expect(typeof createHttpGateway().reports.query).toBe('function')
  })

  it('turns a 401 into an unauthorized ApiError', async () => {
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    await expect(createReportsHttp().fields()).rejects.toMatchObject({ status: 401, kind: 'unauthorized' })
  })
})

describe('reports.query over HTTP', () => {
  it('sends POST /reports/query with the design in snake case', async () => {
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

    await createReportsHttp().query(input)

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

  it('sends no key for what the design leaves out', async () => {
    const { calls } = stubFetch(json(serverResult()))

    await createReportsHttp().query({
      columns: [{ field: 'deal.code', group: false }],
      conditions: [{ field: 'deal.name', operator: 'is_empty' }],
      combine: 'and',
      rowLimit: 100,
    })

    const body = calls[0]?.body as { columns: object[]; conditions: object[] } & Record<string, unknown>
    expect(Object.keys(body).sort()).toEqual(['columns', 'combine', 'conditions', 'row_limit'])
    expect(Object.keys(body.columns[0] ?? {}).sort()).toEqual(['field', 'group'])
    expect('sort' in (body.columns[0] ?? {})).toBe(false)
    expect(Object.keys(body.conditions[0] ?? {}).sort()).toEqual(['field', 'operator'])
  })

  it('maps the result to camel case', async () => {
    stubFetch(json(serverResult({ row_scope: 'action', action_filter: 'join', deal_numbers_once: true, truncated: true, total_count: 12_345 })))

    const result = await createReportsHttp().query(REQUEST)

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
      format: 'krw_thousand',
      prefixLength: null,
      group: false,
      aggregate: 'sum',
    })
  })

  it('keeps a null format and the prefix length of a result column', async () => {
    stubFetch(json(serverResult()))

    const result = await createReportsHttp().query(REQUEST)

    expect(result.columns[0]).toMatchObject({ field: 'deal.vendor', format: null, prefixLength: null })
  })

  it('maps a prefix length on a column of any type', async () => {
    const columns = [{ ...SERVER_COLUMNS[0], prefix_length: 4 }, SERVER_COLUMNS[1]]
    stubFetch(json(serverResult({ columns })))

    const result = await createReportsHttp().query(REQUEST)

    expect(result.columns[0]?.prefixLength).toBe(4)
  })

  it('maps a catalog field without formats to an empty list and a null default', async () => {
    const catalog = serverCatalog()
    stubFetch(json(catalog))

    const mapped = await createReportsHttp().fields()

    const risk = mapped.fields.find((f) => f.key === 'deal.risk')
    expect(risk).toMatchObject({ formats: [], defaultFormat: null })
  })

  it('sends a format only when the design has one', async () => {
    const { calls } = stubFetch(json(serverResult()))

    await createReportsHttp().query({
      columns: [{ field: 'deal.amount', format: 'krw_million', group: false }, { field: 'deal.name', group: false }],
      conditions: [],
      combine: 'and',
      rowLimit: 100,
    })

    const body = calls[0]?.body as { columns: Record<string, unknown>[] }
    expect(body.columns[0]).toEqual({ field: 'deal.amount', format: 'krw_million', group: false })
    expect('format' in (body.columns[1] ?? {})).toBe(false)
  })

  it('keeps null totals when nothing is grouped', async () => {
    stubFetch(json(serverResult({ totals: null })))

    const result = await createReportsHttp().query(REQUEST)

    expect(result.totals).toBeNull()
  })

  it.each([
    ['a row shorter than the columns', { rows: [['Silverfort']] }],
    ['a row longer than the columns', { rows: [['Silverfort', 1, 2]] }],
    ['a totals row of another width', { totals: [null] }],
    ['a boolean cell', { rows: [['Silverfort', true]] }],
    ['an object cell', { rows: [['Silverfort', { a: 1 }]] }],
  ])('rejects %s as a malformed response', async (_name, over) => {
    stubFetch(json(serverResult(over)))

    await expect(createReportsHttp().query(REQUEST)).rejects.toMatchObject({ status: 502, kind: 'malformed-response' })
  })

  it('turns an invalid report problem into reportErrors without throwing a TypeError', async () => {
    const errors = [
      { location: ['columns', 1, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: deal.nope' },
      { location: ['row_limit'], code: 'row-limit-invalid', message: '최대 행 수는 100, 1000, 10000 중 하나여야 합니다' },
    ]
    stubFetch(problem(422, 'invalid-report', '허용되지 않은 필드입니다: deal.nope', { errors }))

    const failure = createReportsHttp().query(REQUEST)

    await expect(failure).rejects.toMatchObject({ status: 422, kind: 'invalid-report' })
    await expect(failure).rejects.toMatchObject({ message: '허용되지 않은 필드입니다: deal.nope' })
    await expect(failure).rejects.toMatchObject({ problem: { reportErrors: errors } })
  })

  it('keeps the request validation problem as a validation error with its field messages', async () => {
    stubFetch(
      problem(422, 'request-validation', '요청 형식이 올바르지 않습니다', {
        errors: [{ loc: ['body', 'columns', 0, 'field'], msg: 'Field required', type: 'missing' }],
      }),
    )

    await expect(createReportsHttp().query(REQUEST)).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '요청 형식이 올바르지 않습니다 — columns.0.field: Field required',
    })
  })

  it('keeps the detail of a report timeout', async () => {
    const detail = '조회가 10초 안에 끝나지 않았습니다. 조건을 좁히거나 컬럼을 줄이세요'
    stubFetch(problem(503, 'report-timeout', detail))

    await expect(createReportsHttp().query(REQUEST)).rejects.toMatchObject({ status: 503, kind: 'report-timeout', message: detail })
  })

  it('maps a lost connection to the network error', async () => {
    stubNetworkDown()

    await expect(createReportsHttp().query(REQUEST)).rejects.toMatchObject({
      status: 0,
      kind: 'network',
      message: '서버에 연결할 수 없습니다.',
    })
  })
})
