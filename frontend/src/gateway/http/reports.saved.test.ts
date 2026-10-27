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
    { field: 'deal.vendor', format: 'name', group: true },
    { field: 'deal.name', format: 'prefix', prefix_length: 5, group: false, label: '이름 앞부분', aggregate: 'count' },
    { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum' },
  ],
  conditions: [
    { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
    { field: 'deal.expected_close', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
    { field: 'deal.name', operator: 'is_empty' },
  ],
  combine: 'or',
  sort: { column: 2, direction: 'desc' },
  row_limit: 10000,
}

const CAMEL_DEFINITION = {
  columns: [
    { field: 'deal.vendor', format: 'name', group: true },
    { field: 'deal.name', format: 'prefix', prefixLength: 5, group: false, label: '이름 앞부분', aggregate: 'count' },
    { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum' },
  ],
  conditions: [
    { field: 'deal.amount', operator: 'between', value: [1_000_000, 2_000_000] },
    { field: 'deal.expected_close', operator: 'relative', value: { period: 'last_n_days', days: 30 } },
    { field: 'deal.name', operator: 'is_empty' },
  ],
  combine: 'or',
  sort: { column: 2, direction: 'desc' },
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
    ...over,
  }
}

const serverDetail = (over: Record<string, unknown> = {}) => ({
  ...serverSummary(),
  revision: 3,
  definition: SERVER_DEFINITION,
  generated_sql: 'SELECT deal.vendor FROM deals',
  ...over,
})

const serverResult = () => ({
  row_scope: 'deal',
  action_filter: 'none',
  deal_numbers_once: false,
  columns: [{ index: 0, field: 'deal.vendor', label: 'Vendor', entity: 'deal', type: 'code', value_type: 'text', format: 'name', prefix_length: null, group: true, aggregate: null }],
  rows: [['Silverfort']],
  totals: null,
  total_count: 1,
  truncated: false,
  row_limit: 1000,
  sql: 'SELECT demo',
  elapsed_ms: 21,
  today: '2026-10-27',
})

const INPUT: SavedReportInput = { name: ' 새 리포트 ', description: '설명', visibility: 'private', definition: CAMEL_DEFINITION as SavedReportInput['definition'] }

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

  it('leaves out the keys a definition does not have', async () => {
    stubFetch(json(serverDetail({ definition: { columns: [{ field: 'deal.code', format: 'as_is', group: false }], conditions: [], combine: 'and', row_limit: 100 } })))

    const { definition } = await createReportsHttp().get(12)

    expect(definition).toEqual({ columns: [{ field: 'deal.code', format: 'as_is', group: false }], conditions: [], combine: 'and', rowLimit: 100 })
    expect('sort' in definition).toBe(false)
    expect('label' in (definition.columns[0] ?? {})).toBe(false)
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
    expect(calls[0]?.body).toEqual({ name: ' 새 리포트 ', description: '설명', visibility: 'private', definition: SERVER_DEFINITION })
    expect(calls[1]).toMatchObject({ method: 'PUT', path: '/api/v1/reports/12' })
    expect(calls[1]?.body).toEqual({ name: ' 새 리포트 ', description: '설명', visibility: 'private', definition: SERVER_DEFINITION, revision: 3 })
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

    expect(Object.keys(calls[0]?.body as object).sort()).toEqual(['definition', 'description', 'name', 'visibility'])
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
