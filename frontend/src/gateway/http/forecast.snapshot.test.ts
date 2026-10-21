import { afterEach, describe, expect, it, vi } from 'vitest'
import { createForecastHttp } from './forecast'
import { createHttpGateway } from './index'
import { json, problem, stubFetch, userRefBody } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const query = (path: string) => new URL(path, 'http://localhost').searchParams

const TAKEN_AT = '2026-10-01T00:05:00+09:00'
const COLUMNS = [
  { key: 'pipeline', name: 'Pipeline', outcome: 'open', order: 1 },
  { key: 'commit', name: '확정(당시)', outcome: 'open', order: 4 },
  { key: 'won', name: 'Won', outcome: 'won', order: 5 },
]

/** 서버 스냅숏 요약 응답(실시간 요약과 같은 모양, basis=snapshot, as_of=생성 시각). */
function serverSnapshotSummary(over: Record<string, unknown> = {}) {
  return {
    basis: 'snapshot',
    as_of: TAKEN_AT,
    snapshot_period: '2026-09',
    period: { year: 2026, quarter: 3, month: null, from: '2026-07-01', to: '2026-09-30' },
    columns: COLUMNS,
    rows: [
      {
        owner: userRefBody(7, '김영업', false, 'sales'),
        cells: [
          { key: 'pipeline', count: 2, amount: 200_000_000 },
          { key: 'commit', count: 1, amount: 50_000_000 },
          { key: 'won', count: 1, amount: 700_000_000 },
        ],
        open_total: { count: 3, amount: 250_000_000 },
      },
    ],
    total: {
      owner: null,
      cells: [
        { key: 'pipeline', count: 2, amount: 200_000_000 },
        { key: 'commit', count: 1, amount: 50_000_000 },
        { key: 'won', count: 1, amount: 700_000_000 },
      ],
      open_total: { count: 3, amount: 250_000_000 },
    },
    ...over,
  }
}

describe('forecast.snapshots over HTTP', () => {
  it('sends GET /forecast/snapshots without any query', async () => {
    const { calls } = stubFetch(json({ items: [] }))

    await createForecastHttp().snapshots()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/forecast/snapshots' })
  })

  it('maps the items to period and takenAt in the order the server gave (newest first)', async () => {
    stubFetch(
      json({
        items: [
          { period: '2026-09', taken_at: TAKEN_AT },
          { period: '2026-08', taken_at: '2026-09-01T00:05:00+09:00' },
        ],
      }),
    )

    const list = await createForecastHttp().snapshots()

    expect(list).toEqual([
      { period: '2026-09', takenAt: TAKEN_AT },
      { period: '2026-08', takenAt: '2026-09-01T00:05:00+09:00' },
    ])
  })

  it('is an empty list when nothing was stored', async () => {
    stubFetch(json({ items: [] }))

    expect(await createForecastHttp().snapshots()).toEqual([])
  })

  it('passes a 401 to the caller', async () => {
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    await expect(createForecastHttp().snapshots()).rejects.toMatchObject({ status: 401 })
  })
})

describe('forecast.snapshotSummary over HTTP', () => {
  it('puts the period in the path and sends only the year when nothing else is set', async () => {
    const { calls } = stubFetch(json(serverSnapshotSummary()))

    await createForecastHttp().snapshotSummary('2026-09', { year: 2026 })

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/forecast/snapshots/2026-09/summary?year=2026' })
  })

  it('maps year, quarter and owner to their snake_case query keys', async () => {
    const { calls } = stubFetch(json(serverSnapshotSummary()))

    await createForecastHttp().snapshotSummary('2026-09', { year: 2026, quarter: 3, ownerId: 7 })

    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ year: '2026', quarter: '3', owner_user_id: '7' })
  })

  it('sends month instead of quarter for a month query', async () => {
    const { calls } = stubFetch(json(serverSnapshotSummary()))

    await createForecastHttp().snapshotSummary('2026-09', { year: 2026, month: 8 })

    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ year: '2026', month: '8' })
  })

  it('never sends a vendor condition even if a caller passes one (a snapshot has no vendor)', async () => {
    const { calls } = stubFetch(json(serverSnapshotSummary()))
    const withVendor = { year: 2026, vendorId: 6 } as { year: number }

    await createForecastHttp().snapshotSummary('2026-09', withVendor)

    expect(query(calls[0]?.path ?? '').has('vendor_id')).toBe(false)
  })

  it('maps basis, the snapshot period and the creation time as asOf', async () => {
    stubFetch(json(serverSnapshotSummary()))

    const summary = await createForecastHttp().snapshotSummary('2026-09', { year: 2026, quarter: 3 })

    expect(summary.basis).toBe('snapshot')
    expect(summary.snapshotPeriod).toBe('2026-09')
    expect(summary.asOf).toBe(TAKEN_AT)
    expect(summary.query).toEqual({ year: 2026, quarter: 3 })
  })

  it('maps the stored columns, rows and the total row like a live summary', async () => {
    stubFetch(json(serverSnapshotSummary()))

    const summary = await createForecastHttp().snapshotSummary('2026-09', { year: 2026, quarter: 3 })

    expect(summary.columns).toEqual(COLUMNS)
    expect(summary.rows.map((r) => [r.ownerId, r.ownerName])).toEqual([[7, '김영업']])
    expect(summary.rows[0]?.cells.commit).toEqual({ count: 1, amount: 50_000_000 })
    expect(summary.rows[0]?.total).toEqual({ count: 3, amount: 250_000_000 })
    expect(summary.totalRow).toMatchObject({ ownerId: null, ownerName: '합계', total: { count: 3, amount: 250_000_000 } })
  })

  it('keeps the live summary free of a snapshot period', async () => {
    stubFetch(json(serverSnapshotSummary({ basis: 'live', snapshot_period: null, as_of: '2026-10-21T14:03:00+09:00' })))

    const summary = await createForecastHttp().summary({ year: 2026, quarter: 3 })

    expect(summary.basis).toBe('live')
    expect(summary.snapshotPeriod).toBeNull()
  })

  it('passes a 404 for a missing period to the caller as an ApiError', async () => {
    stubFetch(problem(404, 'not-found', '해당 기준 월의 스냅숏이 없습니다.'))

    await expect(createForecastHttp().snapshotSummary('2025-01', { year: 2026 })).rejects.toMatchObject({
      status: 404,
      message: '해당 기준 월의 스냅숏이 없습니다.',
    })
  })

  it('passes a 422 problem to the caller', async () => {
    stubFetch(problem(422, 'invalid-value', 'Quarter와 월은 함께 선택할 수 없습니다.'))

    await expect(createForecastHttp().snapshotSummary('2026-09', { year: 2026, quarter: 1, month: 1 })).rejects.toMatchObject({
      status: 422,
    })
  })

  it('is wired into the http gateway', async () => {
    const { calls } = stubFetch(json({ items: [] }), json(serverSnapshotSummary()))
    const gateway = createHttpGateway()

    await gateway.forecast.snapshots()
    await gateway.forecast.snapshotSummary('2026-09', { year: 2026 })

    expect(calls.map((c) => c.path)).toEqual([
      '/api/v1/forecast/snapshots',
      '/api/v1/forecast/snapshots/2026-09/summary?year=2026',
    ])
  })
})
