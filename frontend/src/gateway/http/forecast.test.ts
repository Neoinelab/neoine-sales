import { afterEach, describe, expect, it, vi } from 'vitest'
import { createForecastHttp } from './forecast'
import { createHttpGateway } from './index'
import { json, problem, stubFetch, userRefBody } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const query = (path: string) => new URL(path, 'http://localhost').searchParams

const COLUMNS = [
  { key: 'pipeline', name: 'Pipeline', outcome: 'open', order: 1 },
  { key: 'commit', name: '확정', outcome: 'open', order: 4 },
  { key: 'won', name: 'Won', outcome: 'won', order: 5 },
]

/** 서버 요약 응답(columns 순서와 cells 순서가 같다). */
function serverSummary(over: Record<string, unknown> = {}) {
  return {
    basis: 'live',
    as_of: '2026-10-21T14:03:00+09:00',
    snapshot_period: null,
    period: { year: 2026, quarter: 4, month: null, from: '2026-10-01', to: '2026-12-31' },
    columns: COLUMNS,
    rows: [
      {
        owner: userRefBody(7, '김영업', false, 'sales'),
        cells: [
          { key: 'pipeline', count: 2, amount: 150_000_000 },
          { key: 'commit', count: 1, amount: 7_000_000 },
          { key: 'won', count: 0, amount: 0 },
        ],
        open_total: { count: 3, amount: 157_000_000 },
      },
      {
        owner: userRefBody(9, '강퇴사', true, 'sales'),
        cells: [
          { key: 'pipeline', count: 1, amount: 3 },
          { key: 'commit', count: 0, amount: 0 },
          { key: 'won', count: 1, amount: 9 },
        ],
        open_total: { count: 1, amount: 3 },
      },
    ],
    total: {
      owner: null,
      cells: [
        { key: 'pipeline', count: 3, amount: 150_000_003 },
        { key: 'commit', count: 1, amount: 7_000_000 },
        { key: 'won', count: 1, amount: 9 },
      ],
      open_total: { count: 4, amount: 157_000_003 },
    },
    ...over,
  }
}

describe('forecast.summary over HTTP', () => {
  it('sends GET /forecast/summary with only the year when nothing else is set', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createForecastHttp().summary({ year: 2026 })

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/forecast/summary?year=2026' })
  })

  it('maps every condition to its snake_case query key', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createForecastHttp().summary({ year: 2026, quarter: 4, vendorId: 6, ownerId: 7 })

    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({
      year: '2026',
      quarter: '4',
      vendor_id: '6',
      owner_user_id: '7',
    })
  })

  it('sends month instead of quarter for a month query', async () => {
    const { calls } = stubFetch(json(serverSummary({ period: { year: 2026, quarter: null, month: 3, from: '2026-03-01', to: '2026-03-31' } })))

    await createForecastHttp().summary({ year: 2026, month: 3 })

    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ year: '2026', month: '3' })
  })

  it('does not send empty conditions', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createForecastHttp().summary({ year: 2026, quarter: undefined, vendorId: undefined, ownerId: undefined })

    expect(query(calls[0]?.path ?? '').has('quarter')).toBe(false)
    expect(query(calls[0]?.path ?? '').has('vendor_id')).toBe(false)
    expect(query(calls[0]?.path ?? '').has('owner_user_id')).toBe(false)
  })

  it('maps columns with their order and outcome', async () => {
    stubFetch(json(serverSummary()))

    const summary = await createForecastHttp().summary({ year: 2026, quarter: 4 })

    expect(summary.columns).toEqual(COLUMNS)
  })

  it('turns the cell list into a record by key and keeps the owner label as the name', async () => {
    stubFetch(json(serverSummary()))

    const summary = await createForecastHttp().summary({ year: 2026, quarter: 4 })

    expect(summary.rows.map((r) => [r.ownerId, r.ownerName])).toEqual([
      [7, '김영업'],
      [9, '강퇴사(퇴사)'],
    ])
    expect(summary.rows[0]?.cells).toEqual({
      pipeline: { count: 2, amount: 150_000_000 },
      commit: { count: 1, amount: 7_000_000 },
      won: { count: 0, amount: 0 },
    })
    expect(summary.rows[0]?.total).toEqual({ count: 3, amount: 157_000_000 })
  })

  it('maps the total row without an owner', async () => {
    stubFetch(json(serverSummary()))

    const { totalRow } = await createForecastHttp().summary({ year: 2026, quarter: 4 })

    expect(totalRow).toMatchObject({ ownerId: null, ownerName: '합계', total: { count: 4, amount: 157_000_003 } })
    expect(totalRow.cells.pipeline).toEqual({ count: 3, amount: 150_000_003 })
  })

  it('keeps the basis and the as-of time and echoes the query', async () => {
    stubFetch(json(serverSummary()))

    const summary = await createForecastHttp().summary({ year: 2026, quarter: 4, ownerId: 7 })

    expect(summary.basis).toBe('live')
    expect(summary.asOf).toBe('2026-10-21T14:03:00+09:00')
    expect(summary.query).toEqual({ year: 2026, quarter: 4, ownerId: 7 })
  })

  it('has no rows when the server has none', async () => {
    stubFetch(json(serverSummary({ rows: [] })))

    const summary = await createForecastHttp().summary({ year: 2031 })

    expect(summary.rows).toEqual([])
  })

  it('passes a 422 invalid-value problem to the caller as an ApiError', async () => {
    stubFetch(problem(422, 'invalid-value', 'Quarter와 월은 함께 선택할 수 없습니다.'))

    await expect(createForecastHttp().summary({ year: 2026, quarter: 1, month: 1 })).rejects.toMatchObject({
      status: 422,
      message: 'Quarter와 월은 함께 선택할 수 없습니다.',
    })
  })

  it('passes a 401 to the caller', async () => {
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    await expect(createForecastHttp().summary({ year: 2026 })).rejects.toMatchObject({ status: 401 })
  })

  it('is wired into the http gateway (no longer a 501 stub)', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createHttpGateway().forecast.summary({ year: 2026 })

    expect(calls).toHaveLength(1)
    expect(calls[0]?.path).toBe('/api/v1/forecast/summary?year=2026')
  })
})
