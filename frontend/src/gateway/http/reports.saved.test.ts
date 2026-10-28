import { afterEach, describe, expect, it, vi } from 'vitest'
import type { SavedReportInput } from '../../shared/model/reportTypes'
import { serverUserRef } from '../../test/fixtures/serverDeal'
import { USER_ID } from '../../test/fake/seed/ids'
import { createHttpGateway } from './index'
import { createReportsHttp } from './reports'
import { json, noContent, problem, stubFetch, stubNetworkDown } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

/** 저장 리포트 HTTP 어댑터(Reports 3단계 G1~G3, 계획 4.7). 서버 JSON은 snake_case, 화면 모델은 camelCase. */

const SERVER_DEFINITION = {
  columns: [
    { field: 'deal.vendor', group: true },
    { field: 'deal.name', prefix_length: 5, group: false, label: '이름 앞부분', aggregate: 'count' },
    { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum', sort: 'desc' },
  ],
  conditions: [
    { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
    { field: 'deal.expected_close', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
    { field: 'deal.name', operator: 'is_empty' },
  ],
  combine: 'or',
  row_limit: 10000,
}

const CAMEL_DEFINITION = {
  columns: [
    { field: 'deal.vendor', group: true },
    { field: 'deal.name', prefixLength: 5, group: false, label: '이름 앞부분', aggregate: 'count' },
    { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum', sort: 'desc' },
  ],
  conditions: [
    { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
    { field: 'deal.expected_close', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
    { field: 'deal.name', operator: 'is_empty' },
  ],
  combine: 'or',
  rowLimit: 10000,
}

function serverSummary(over: Record<string, unknown> = {}) {
  return {
    id: 12,
    name: 'Vendor별 분기 Pipeline',
    description: 'Lost 제외, 올해 Expected Close',
    visibility: 'public',
    owner: serverUserRef({ id: USER_ID.kim }),
    updated_by: serverUserRef({ id: USER_ID.old, name: '강퇴사', label: '강퇴사(퇴사)', resigned: true }),
    entities: ['deal', 'action'],
    created_at: '2026-10-24T17:20:00+09:00',
    updated_at: '2026-10-25T09:00:00+09:00',
    chart_kind: null,
    ...over,
  }
}

const SERVER_CHART = {
  kind: 'stacked_bar',
  category: 0,
  series: 1,
  values: [2],
  swap: true,
  title: '분기 Pipeline',
  legend: 'right',
  data_labels: true,
  category_axis_title: 'Vendor',
  value_axis_title: '금액',
  value_min: 0,
  value_max: 12.5,
  secondary_axis: false,
}

const CAMEL_CHART = {
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

const serverDetail = (over: Record<string, unknown> = {}) => ({
  ...serverSummary(),
  revision: 3,
  definition: SERVER_DEFINITION,
  generated_sql: 'SELECT deal.vendor FROM deals',
  chart: null,
  chart_problem: null,
  ...over,
})

const serverResult = () => ({
  row_scope: 'deal',
  action_filter: 'none',
  deal_numbers_once: false,
  columns: [{ index: 0, field: 'deal.vendor', label: 'Vendor', entity: 'deal', type: 'code', value_type: 'text', format: null, prefix_length: null, group: true, aggregate: null }],
  rows: [['Silverfort']],
  totals: null,
  total_count: 1,
  truncated: false,
  row_limit: 1000,
  sql: 'SELECT demo',
  elapsed_ms: 21,
  today: '2026-10-27',
})

const INPUT: SavedReportInput = {
  name: ' 새 리포트 ',
  description: '설명',
  visibility: 'private',
  definition: CAMEL_DEFINITION as SavedReportInput['definition'],
  chart: null,
}

describe('saved reports over HTTP: reading', () => {
  it('sends GET /reports and maps summaries to camel case', async () => {
    const { calls } = stubFetch(json([serverSummary(), serverSummary({ id: 9, visibility: 'private', entities: ['deal'] })]))

    const list = await createReportsHttp().list()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/reports' })
    expect(list).toHaveLength(2)
    expect(list[0]).toEqual({
      id: 12,
      name: 'Vendor별 분기 Pipeline',
      description: 'Lost 제외, 올해 Expected Close',
      visibility: 'public',
      owner: { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' },
      updatedBy: { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' },
      entities: ['deal', 'action'],
      createdAt: '2026-10-24T17:20:00+09:00',
      updatedAt: '2026-10-25T09:00:00+09:00',
      chartKind: null,
    })
    expect(list[1]).toMatchObject({ id: 9, visibility: 'private', entities: ['deal'] })
  })

  it('maps summaries and detail with definition to camel case', async () => {
    const { calls } = stubFetch(json(serverDetail()))

    const report = await createReportsHttp().get(12)

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/reports/12' })
    expect(report).toMatchObject({ id: 12, revision: 3, generatedSql: 'SELECT deal.vendor FROM deals', owner: { id: USER_ID.kim }, entities: ['deal', 'action'] })
    expect(report.definition).toEqual(CAMEL_DEFINITION)
  })

  it('maps a null format of a stored definition to no format key', async () => {
    const definition = { columns: [{ field: 'deal.name', format: null, group: false }], conditions: [], combine: 'and', row_limit: 100 }
    stubFetch(json(serverDetail({ definition })))

    const { definition: mapped } = await createReportsHttp().get(12)

    expect('format' in (mapped.columns[0] ?? {})).toBe(false)
  })

  it('leaves out the keys a definition does not have', async () => {
    stubFetch(json(serverDetail({ definition: { columns: [{ field: 'deal.code', group: false }], conditions: [], combine: 'and', row_limit: 100 } })))

    const { definition } = await createReportsHttp().get(12)

    expect(definition).toEqual({ columns: [{ field: 'deal.code', group: false }], conditions: [], combine: 'and', rowLimit: 100 })
    expect('sort' in definition).toBe(false)
    expect('label' in (definition.columns[0] ?? {})).toBe(false)
  })

  it('reads the sort of each column and drops values it does not know', async () => {
    const columns = [
      { field: 'deal.code', group: false, sort: 'asc' },
      { field: 'deal.name', group: false, sort: null },
      { field: 'deal.vendor', group: false, sort: 'desc' },
      { field: 'deal.owner', group: false, sort: 'sideways' },
    ]
    stubFetch(json(serverDetail({ definition: { columns, conditions: [], combine: 'and', row_limit: 100 } })))

    const { definition } = await createReportsHttp().get(12)

    expect(definition.columns.map((c) => c.sort)).toEqual(['asc', undefined, 'desc', undefined])
    expect('sort' in (definition.columns[1] ?? {})).toBe(false)
    expect('sort' in definition).toBe(false)
  })

  it('is wired into the HTTP gateway as reports', () => {
    const reports = createHttpGateway().reports

    for (const name of ['list', 'get', 'create', 'update', 'copy', 'remove', 'run'] as const) expect(typeof reports[name]).toBe('function')
  })

  it('runs a saved report with POST /reports/{id}/run and maps it like a query', async () => {
    const { calls } = stubFetch(json(serverResult()))

    const result = await createReportsHttp().run(12)

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/reports/12/run' })
    expect(calls[0]?.body).toBeUndefined()
    expect(result).toMatchObject({ rowScope: 'deal', totalCount: 1, rowLimit: 1000, today: '2026-10-27', rows: [['Silverfort']] })
  })
})

describe('saved reports over HTTP: writing', () => {
  it('sends create, update with revision, copy and run in snake case', async () => {
    const { calls } = stubFetch(json(serverDetail(), 201, { Location: '/api/v1/reports/12' }), json(serverDetail({ revision: 4 })), json(serverDetail({ id: 13 }), 201), noContent())
    const http = createReportsHttp()

    const created = await http.create(INPUT)
    const updated = await http.update(12, { ...INPUT, revision: 3 })
    const copied = await http.copy(12, { name: '복사본', description: '', visibility: 'public' })
    await http.remove(12)

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/reports' })
    expect(calls[0]?.body).toEqual({ name: ' 새 리포트 ', description: '설명', visibility: 'private', definition: SERVER_DEFINITION, chart: null })
    expect(calls[1]).toMatchObject({ method: 'PUT', path: '/api/v1/reports/12' })
    expect(calls[1]?.body).toEqual({ name: ' 새 리포트 ', description: '설명', visibility: 'private', definition: SERVER_DEFINITION, chart: null, revision: 3 })
    expect(calls[2]).toMatchObject({ method: 'POST', path: '/api/v1/reports/12/copy' })
    expect(calls[2]?.body).toEqual({ name: '복사본', description: '', visibility: 'public' })
    expect(calls[3]).toMatchObject({ method: 'DELETE', path: '/api/v1/reports/12' })
    expect(created.revision).toBe(3)
    expect(updated.revision).toBe(4)
    expect(copied.id).toBe(13)
  })

  it('never sends SQL, ids or owners in a create body', async () => {
    const { calls } = stubFetch(json(serverDetail(), 201))

    await createReportsHttp().create(INPUT)

    expect(Object.keys(calls[0]?.body as object).sort()).toEqual(['chart', 'definition', 'description', 'name', 'visibility'])
  })

  it('resolves a delete without a body', async () => {
    stubFetch(noContent())

    await expect(createReportsHttp().remove(12)).resolves.toBeUndefined()
  })
})

describe('saved reports over HTTP: errors', () => {
  const issues = [
    { location: ['columns', 0, 'field'], code: 'unknown-field', message: '허용되지 않은 필드입니다: deal.nope' },
    { location: ['row_limit'], code: 'row-limit-invalid', message: '최대 행 수가 올바르지 않습니다' },
  ]
  const invalidBody = () => problem(422, 'invalid-report', '허용되지 않은 필드입니다: deal.nope', { errors: issues })

  it.each([
    ['create', (h: ReturnType<typeof createReportsHttp>) => h.create(INPUT)],
    ['update', (h: ReturnType<typeof createReportsHttp>) => h.update(12, { ...INPUT, revision: 3 })],
    ['copy', (h: ReturnType<typeof createReportsHttp>) => h.copy(12, { name: 'a', description: '', visibility: 'public' })],
    ['run', (h: ReturnType<typeof createReportsHttp>) => h.run(12)],
  ])('moves invalid report errors into reportErrors for %s', async (_name, call) => {
    stubFetch(invalidBody())

    const error = await call(createReportsHttp()).catch((e: unknown) => e)

    expect(error).toMatchObject({ status: 422, kind: 'invalid-report', message: '허용되지 않은 필드입니다: deal.nope' })
    expect((error as { problem: { reportErrors: unknown } }).problem.reportErrors).toEqual(issues)
  })

  it('keeps the two 409 kinds apart so the screen can tell a duplicate name from a conflict', async () => {
    stubFetch(problem(409, 'already-exists', '같은 이름의 리포트가 이미 있습니다.'), problem(409, 'invalid-state', '다른 사용자가 먼저 이 리포트를 저장했습니다.'))
    const http = createReportsHttp()

    const duplicate = await http.create(INPUT).catch((e: unknown) => e)
    const conflict = await http.update(12, { ...INPUT, revision: 1 }).catch((e: unknown) => e)

    expect(duplicate).toMatchObject({ status: 409, kind: 'already-exists', message: '같은 이름의 리포트가 이미 있습니다.' })
    expect(conflict).toMatchObject({ status: 409, kind: 'invalid-state', message: '다른 사용자가 먼저 이 리포트를 저장했습니다.' })
  })

  it.each([
    [404, 'not-found', 'not-found'],
    [403, 'forbidden', 'forbidden'],
    [422, 'invalid-value', 'validation'],
    [422, 'request-validation', 'validation'],
    [401, 'unauthenticated', 'unauthorized'],
  ] as const)('turns %s %s into the %s kind with the server message', async (status, serverKind, kind) => {
    stubFetch(problem(status, serverKind, '서버 문구'))

    await expect(createReportsHttp().remove(12)).rejects.toMatchObject({ status, kind, message: '서버 문구' })
  })

  it('turns a lost connection into the network error', async () => {
    stubNetworkDown()

    await expect(createReportsHttp().list()).rejects.toMatchObject({ status: 0, kind: 'network' })
    await expect(createReportsHttp().create(INPUT)).rejects.toMatchObject({ status: 0, kind: 'network' })
  })

  it('maps a report timeout on run', async () => {
    stubFetch(problem(503, 'report-timeout', '조회가 10초 안에 끝나지 않았습니다.'))

    await expect(createReportsHttp().run(12)).rejects.toMatchObject({ status: 503, kind: 'report-timeout' })
  })
})


describe('saved reports over HTTP: chart (Reports 4단계 G1, G2)', () => {
  it('maps the chart of a detail and its chart problem to camel case', async () => {
    stubFetch(json(serverDetail({ chart: SERVER_CHART })), json(serverDetail({ chart: null, chart_problem: '저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.' })))
    const http = createReportsHttp()

    const withChart = await http.get(12)
    const broken = await http.get(12)

    expect(withChart.chart).toEqual(CAMEL_CHART)
    expect(withChart.chartProblem).toBeNull()
    expect(broken.chart).toBeNull()
    expect(broken.chartProblem).toBe('저장된 차트 설정을 읽을 수 없어 차트 없이 열었습니다. 차트를 다시 만들어 저장하세요.')
  })

  it('keeps a null range and a null series of the chart', async () => {
    stubFetch(json(serverDetail({ chart: { ...SERVER_CHART, series: null, value_min: null, value_max: null } })))

    const { chart } = await createReportsHttp().get(12)

    expect(chart).toMatchObject({ series: null, valueMin: null, valueMax: null })
  })

  it('maps the chart kind of a list item', async () => {
    stubFetch(json([serverSummary({ chart_kind: 'doughnut' }), serverSummary({ id: 9, chart_kind: null })]))

    const list = await createReportsHttp().list()

    expect(list.map((r) => r.chartKind)).toEqual(['doughnut', null])
  })

  it.each([
    ['an unknown kind', { kind: 'radar' }],
    ['an unknown legend position', { legend: 'left' }],
  ])('treats %s in a response as a malformed response', async (_name, over) => {
    stubFetch(json(serverDetail({ chart: { ...SERVER_CHART, ...over } })))

    const error = await createReportsHttp().get(12).catch((e: unknown) => e)

    expect(error).toMatchObject({ kind: 'malformed-response' })
  })

  it('treats an unknown chart kind in a list item as a malformed response', async () => {
    stubFetch(json([serverSummary({ chart_kind: 'radar' })]))

    const error = await createReportsHttp().list().catch((e: unknown) => e)

    expect(error).toMatchObject({ kind: 'malformed-response' })
  })

  it('sends the chart in snake case in create and update bodies', async () => {
    const { calls } = stubFetch(json(serverDetail({ chart: SERVER_CHART }), 201), json(serverDetail({ chart: SERVER_CHART })))
    const http = createReportsHttp()

    await http.create({ ...INPUT, chart: CAMEL_CHART as SavedReportInput['chart'] })
    await http.update(12, { ...INPUT, chart: CAMEL_CHART as SavedReportInput['chart'], revision: 3 })

    expect((calls[0]?.body as { chart: unknown }).chart).toEqual(SERVER_CHART)
    expect((calls[1]?.body as { chart: unknown }).chart).toEqual(SERVER_CHART)
  })

  it('sends null as the chart when there is none so an overwrite clears it', async () => {
    const { calls } = stubFetch(json(serverDetail(), 201), json(serverDetail()))
    const http = createReportsHttp()

    await http.create(INPUT)
    await http.update(12, { ...INPUT, revision: 3 })

    expect(calls[0]?.body).toHaveProperty('chart', null)
    expect(calls[1]?.body).toHaveProperty('chart', null)
  })

  it('sends an incomplete chart as it is so the server answers with positions', async () => {
    const { calls } = stubFetch(json(serverDetail(), 201))
    const incomplete = { ...CAMEL_CHART, category: null, valueMin: 'abc' } as unknown as SavedReportInput['chart']

    await createReportsHttp().create({ ...INPUT, chart: incomplete })

    expect((calls[0]?.body as { chart: Record<string, unknown> }).chart).toMatchObject({ category: null, value_min: 'abc' })
  })

  it('does not send a chart with a copy', async () => {
    const { calls } = stubFetch(json(serverDetail({ id: 13 }), 201))

    await createReportsHttp().copy(12, { name: '복사본', description: '', visibility: 'public' })

    expect(calls[0]?.body).toEqual({ name: '복사본', description: '', visibility: 'public' })
  })

  it('moves a chart location of an invalid report error into reportErrors', async () => {
    const issues = [{ location: ['chart', 'values', 1], code: 'chart-value-invalid', message: '값 열은 숫자(집계) 컬럼이어야 합니다' }]
    stubFetch(problem(422, 'invalid-report', '값 열은 숫자(집계) 컬럼이어야 합니다', { errors: issues }))

    const error = await createReportsHttp().create(INPUT).catch((e: unknown) => e)

    expect((error as { problem: { reportErrors: unknown } }).problem.reportErrors).toEqual(issues)
  })
})
