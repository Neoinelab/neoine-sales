import { api } from '../../shared/api/client'
import type { Schemas } from '../../shared/api/client'
import type { DashboardQuarter, DashboardQuery, DashboardSummary, ForecastCell } from '../../shared/model/types'
import type { DashboardGateway } from '../types'
import { malformedResponse, unwrap } from './request'

type Response = Schemas['DashboardSummaryResponse']
type Cell = Schemas['CellResponse']

const toCell = (cell: { count: number; amount: number }): ForecastCell => ({ count: cell.count, amount: cell.amount })

/** 서버 셀 목록 → key별 Record. columns에 있는데 목록에 없는 key는 0으로 채운다. */
function cellsByKey(list: readonly Cell[], keys: readonly string[]): Record<string, ForecastCell> {
  const byKey = new Map(list.map((c) => [c.key, c]))
  const cells: Record<string, ForecastCell> = {}
  for (const key of keys) {
    const cell = byKey.get(key)
    cells[key] = cell ? toCell(cell) : { count: 0, amount: 0 }
  }
  return cells
}

function toQuarterNumber(value: number): 1 | 2 | 3 | 4 {
  if (value === 1 || value === 2 || value === 3 || value === 4) return value
  throw malformedResponse()
}

function toQuarter(row: Schemas['QuarterClosingResponse'], keys: readonly string[]): DashboardQuarter {
  return {
    quarter: toQuarterNumber(row.quarter),
    from: row.from,
    to: row.to,
    cells: cellsByKey(row.cells, keys),
    openTotal: toCell(row.open_total),
    total: toCell(row.total),
  }
}

function toSummary(body: Response): DashboardSummary {
  const keys = body.forecasts.columns.map((c) => c.key)
  const { attention } = body
  return {
    asOf: body.as_of,
    today: body.today,
    period: { year: body.period.year, quarter: body.period.quarter, from: body.period.from, to: body.period.to },
    forecast: {
      columns: body.forecasts.columns.map((c) => ({ key: c.key, name: c.name, outcome: c.outcome === 'won' ? 'won' : 'open', order: c.order })),
      cells: cellsByKey(body.forecasts.cells, keys),
      openTotal: toCell(body.forecasts.open_total),
    },
    statuses: {
      items: body.statuses.items.map((i) => ({ key: i.key, name: i.name, order: i.order, count: i.count, amount: i.amount })),
      total: toCell(body.statuses.total),
    },
    quarters: body.quarters.map((q) => toQuarter(q, keys)),
    attention: {
      staleDays: attention.stale_days,
      overdue: attention.overdue,
      stale: attention.stale,
      closingThisMonth: { year: attention.closing_this_month.year, month: attention.closing_this_month.month, count: attention.closing_this_month.count },
      closingThisQuarter: {
        year: attention.closing_this_quarter.year,
        quarter: attention.closing_this_quarter.quarter,
        count: attention.closing_this_quarter.count,
      },
    },
  }
}

/** 지정하지 않은 조건은 보내지 않는다. Dashboard는 월 조건이 없다. */
function toQueryParams(q: DashboardQuery) {
  return {
    year: q.year,
    ...(q.quarter !== undefined ? { quarter: q.quarter } : {}),
    ...(q.ownerId !== undefined ? { owner_user_id: q.ownerId } : {}),
    ...(q.vendorId !== undefined ? { vendor_id: q.vendorId } : {}),
  }
}

export function createDashboardHttp(): DashboardGateway {
  return {
    summary: async (query) => toSummary(await unwrap(api.GET('/api/v1/dashboard/summary', { params: { query: toQueryParams(query) } }))),
  }
}
