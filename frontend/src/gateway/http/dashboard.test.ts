import { afterEach, describe, expect, it, vi } from 'vitest'
import { createDashboardHttp } from './dashboard'
import { createHttpGateway } from './index'
import { json, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const query = (path: string) => new URL(path, 'http://localhost').searchParams

const COLUMNS = [
  { key: 'pipeline', name: 'Pipeline', outcome: 'open', order: 1 },
  { key: 'commit', name: '확정', outcome: 'open', order: 4 },
  { key: 'won', name: 'Won', outcome: 'won', order: 5 },
]

/** 서버 요약 응답(plan 4.4 응답 예시 모양). cells는 columns와 같은 순서의 목록이다. */
function serverSummary(over: Record<string, unknown> = {}) {
  return {
    as_of: '2026-10-23T09:00:00+09:00',
    today: '2026-10-23',
    period: { year: 2026, quarter: null, quarters: [], from: '2026-01-01', to: '2026-12-31' },
    forecasts: {
      columns: COLUMNS,
      cells: [
        { key: 'pipeline', count: 18, amount: 320_000_000 },
        { key: 'commit', count: 3, amount: 70_000_000 },
        { key: 'won', count: 2, amount: 40_000_000 },
      ],
      open_total: { count: 21, amount: 390_000_000 },
    },
    statuses: {
      items: [
        { key: 'prospecting', name: '기회발굴', order: 1, count: 18, amount: 320_000_000 },
        { key: 'contract_completed', name: '계약완료', order: 7, count: 2, amount: 40_000_000 },
      ],
      total: { count: 20, amount: 360_000_000 },
    },
    quarters: [1, 2, 3, 4].map((quarter) => ({
      quarter,
      from: `2026-${String(quarter * 3 - 2).padStart(2, '0')}-01`,
      to: ['2026-03-31', '2026-06-30', '2026-09-30', '2026-12-31'][quarter - 1],
      cells: [
        { key: 'pipeline', count: quarter, amount: quarter * 10 },
        { key: 'commit', count: 0, amount: 0 },
        { key: 'won', count: 1, amount: 5 },
      ],
      open_total: { count: quarter, amount: quarter * 10 },
      total: { count: quarter + 1, amount: quarter * 10 + 5 },
    })),
    attention: {
      stale_days: 14,
      overdue: 4,
      stale: 5,
      closing_this_month: { year: 2026, month: 10, count: 4 },
      closing_this_quarter: { year: 2026, quarter: 4, count: 7 },
    },
    ...over,
  }
}

describe('dashboard.summary over HTTP', () => {
  it('sends GET /dashboard/summary with only the year when nothing else is set', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createDashboardHttp().summary({ year: 2026 })

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/dashboard/summary?year=2026' })
  })

  it('maps every condition to its snake_case query key', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createDashboardHttp().summary({ year: 2026, quarters: [4], ownerId: 7, vendorId: 6 })

    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({
      year: '2026',
      quarter: '4',
      owner_user_id: '7',
      vendor_id: '6',
    })
  })

  it('does not send empty conditions and never sends a month', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createDashboardHttp().summary({ year: 2026, quarters: undefined, ownerId: undefined, vendorId: undefined })

    const sent = query(calls[0]?.path ?? '')
    expect([...sent.keys()]).toEqual(['year'])
  })

  it('keeps the as-of time, the business date and the period', async () => {
    stubFetch(json(serverSummary()))

    const summary = await createDashboardHttp().summary({ year: 2026 })

    expect(summary.asOf).toBe('2026-10-23T09:00:00+09:00')
    expect(summary.today).toBe('2026-10-23')
    expect(summary.period).toEqual({ year: 2026, quarter: null, quarters: [], from: '2026-01-01', to: '2026-12-31' })
  })

  it('maps the forecast columns and turns the cell list into a record by key', async () => {
    stubFetch(json(serverSummary()))

    const { forecast } = await createDashboardHttp().summary({ year: 2026 })

    expect(forecast.columns).toEqual(COLUMNS)
    expect(forecast.cells).toEqual({
      pipeline: { count: 18, amount: 320_000_000 },
      commit: { count: 3, amount: 70_000_000 },
      won: { count: 2, amount: 40_000_000 },
    })
    expect(forecast.openTotal).toEqual({ count: 21, amount: 390_000_000 })
  })

  it('fills a column the server did not list a cell for with zero', async () => {
    const body = serverSummary()
    body.forecasts.cells = body.forecasts.cells.filter((c) => c.key !== 'commit')
    stubFetch(json(body))

    const { forecast } = await createDashboardHttp().summary({ year: 2026 })

    expect(forecast.cells.commit).toEqual({ count: 0, amount: 0 })
  })

  it('maps the status items in the server order with the total', async () => {
    stubFetch(json(serverSummary()))

    const { statuses } = await createDashboardHttp().summary({ year: 2026 })

    expect(statuses.items).toEqual([
      { key: 'prospecting', name: '기회발굴', order: 1, count: 18, amount: 320_000_000 },
      { key: 'contract_completed', name: '계약완료', order: 7, count: 2, amount: 40_000_000 },
    ])
    expect(statuses.total).toEqual({ count: 20, amount: 360_000_000 })
  })

  it('maps the four quarters with their range, cells record, open total and total', async () => {
    stubFetch(json(serverSummary()))

    const { quarters } = await createDashboardHttp().summary({ year: 2026 })

    expect(quarters.map((q) => q.quarter)).toEqual([1, 2, 3, 4])
    expect(quarters[3]).toEqual({
      quarter: 4,
      from: '2026-10-01',
      to: '2026-12-31',
      cells: { pipeline: { count: 4, amount: 40 }, commit: { count: 0, amount: 0 }, won: { count: 1, amount: 5 } },
      openTotal: { count: 4, amount: 40 },
      total: { count: 5, amount: 45 },
    })
  })

  it('maps the attention block to camelCase', async () => {
    stubFetch(json(serverSummary()))

    const { attention } = await createDashboardHttp().summary({ year: 2026 })

    expect(attention).toEqual({
      staleDays: 14,
      overdue: 4,
      stale: 5,
      closingThisMonth: { year: 2026, month: 10, count: 4 },
      closingThisQuarter: { year: 2026, quarter: 4, count: 7 },
    })
  })

  it('keeps a chosen quarter in the period', async () => {
    stubFetch(json(serverSummary({ period: { year: 2026, quarter: 3, quarters: [3], from: '2026-07-01', to: '2026-09-30' } })))

    const { period } = await createDashboardHttp().summary({ year: 2026, quarters: [3] })

    expect(period).toEqual({ year: 2026, quarter: 3, quarters: [3], from: '2026-07-01', to: '2026-09-30' })
  })

  it('repeats the quarter key once per chosen quarter', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createDashboardHttp().summary({ year: 2026, quarters: [1, 3] })

    expect(query(calls[0]?.path ?? '').getAll('quarter')).toEqual(['1', '3'])
  })

  it('sends no quarter key for an empty quarter list', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createDashboardHttp().summary({ year: 2026, quarters: [] })

    expect(query(calls[0]?.path ?? '').has('quarter')).toBe(false)
  })

  it('maps several chosen quarters in the period', async () => {
    stubFetch(json(serverSummary({ period: { year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' } })))

    const { period } = await createDashboardHttp().summary({ year: 2026, quarters: [1, 3] })

    expect(period).toEqual({ year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' })
  })

  it.each([[[0]], [[5]], [[1, 7]]])('rejects the period quarters %j as a malformed response', async (quarters) => {
    stubFetch(json(serverSummary({ period: { year: 2026, quarter: null, quarters, from: '2026-01-01', to: '2026-12-31' } })))

    await expect(createDashboardHttp().summary({ year: 2026 })).rejects.toMatchObject({ kind: 'malformed-response' })
  })

  it('passes a 422 request-validation problem to the caller as an ApiError', async () => {
    stubFetch(problem(422, 'request-validation', '요청 값이 올바르지 않습니다.'))

    await expect(createDashboardHttp().summary({ year: 1899 })).rejects.toMatchObject({
      status: 422,
      message: '요청 값이 올바르지 않습니다.',
    })
  })

  it('passes a 401 to the caller', async () => {
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    await expect(createDashboardHttp().summary({ year: 2026 })).rejects.toMatchObject({ status: 401 })
  })

  it('is wired into the http gateway', async () => {
    const { calls } = stubFetch(json(serverSummary()))

    await createHttpGateway().dashboard.summary({ year: 2026 })

    expect(calls).toHaveLength(1)
    expect(calls[0]?.path).toBe('/api/v1/dashboard/summary?year=2026')
  })
})
