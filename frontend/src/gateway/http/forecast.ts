import { api } from '../../shared/api/client'
import type { Schemas } from '../../shared/api/client'
import type { ForecastCell, ForecastQuery, ForecastSummary, ForecastSummaryRow } from '../../shared/model/types'
import type { ForecastGateway } from '../types'
import { unwrap } from './request'

type SnapshotQuery = Omit<ForecastQuery, 'vendorId'>

function toQueryParams(q: SnapshotQuery) {
  return {
    year: q.year,
    ...(q.quarter !== undefined ? { quarter: q.quarter } : {}),
    ...(q.month !== undefined ? { month: q.month } : {}),
    ...(q.ownerId !== undefined ? { owner_user_id: q.ownerId } : {}),
  }
}

const toCell = (cell: { count: number; amount: number }): ForecastCell => ({ count: cell.count, amount: cell.amount })

function toRow(row: Schemas['RowResponse'], keys: readonly string[]): ForecastSummaryRow {
  const byKey = new Map(row.cells.map((c) => [c.key, c]))
  const cells: Record<string, ForecastCell> = {}
  for (const key of keys) {
    const cell = byKey.get(key)
    cells[key] = cell ? toCell(cell) : { count: 0, amount: 0 }
  }
  return {
    ownerId: row.owner?.id ?? null,
    ownerName: row.owner?.label ?? '합계',
    cells,
    total: toCell(row.open_total),
  }
}

function toSummary(body: Schemas['ForecastSummaryResponse'], query: ForecastQuery): ForecastSummary {
  const keys = body.columns.map((c) => c.key)
  return {
    basis: body.basis,
    asOf: body.as_of,
    snapshotPeriod: body.snapshot_period ?? null,
    query: { ...query },
    columns: body.columns.map((c) => ({ key: c.key, name: c.name, outcome: c.outcome === 'won' ? 'won' : 'open', order: c.order })),
    rows: body.rows.map((r) => toRow(r, keys)),
    totalRow: toRow(body.total, keys),
  }
}

export function createForecastHttp(): ForecastGateway {
  return {
    summary: async (query) => {
      const body = await unwrap(
        api.GET('/api/v1/forecast/summary', {
          params: { query: { ...toQueryParams(query), ...(query.vendorId !== undefined ? { vendor_id: query.vendorId } : {}) } },
        }),
      )
      return toSummary(body, query)
    },
    snapshots: async () => {
      const body = await unwrap(api.GET('/api/v1/forecast/snapshots'))
      return body.items.map((i) => ({ period: i.period, takenAt: i.taken_at }))
    },
    snapshotSummary: async (period, query) => {
      // 스냅숏에는 Vendor 조건이 없다(서버 422). 호출자가 vendorId를 넘겨도 보내지 않는다.
      const { year, quarter, month, ownerId } = query
      const clean: SnapshotQuery = { year, ...(quarter !== undefined ? { quarter } : {}), ...(month !== undefined ? { month } : {}), ...(ownerId !== undefined ? { ownerId } : {}) }
      const body = await unwrap(
        api.GET('/api/v1/forecast/snapshots/{period}/summary', { params: { path: { period }, query: toQueryParams(clean) } }),
      )
      return toSummary(body, clean)
    },
  }
}
