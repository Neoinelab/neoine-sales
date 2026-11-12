import type { ForecastGateway } from '../../../gateway/types'
import { inPeriod, periodOf, userLabel } from '../../../shared/model/period'
import type {
  Deal,
  ForecastCell,
  ForecastColumn,
  ForecastQuery,
  ForecastSummary,
  ForecastSummaryRow,
  UserRef,
} from '../../../shared/model/types'
import { QUARTER_MONTH_EXCLUSIVE, validation } from '../errors'
import { read, requireUser, type MockContext } from './context'
import { codeSetOf } from './dealChange'
import { listSnapshots, orderedRows, snapshotSummary } from './forecastSnapshots'
import { userRef } from './views'

const emptyCell = (): ForecastCell => ({ count: 0, amount: 0 })

function add(cell: ForecastCell, deal: Deal): void {
  cell.count += 1
  cell.amount += deal.revenueAmount
}

/** 연 / 연+분기 / 연+월 기간에 속하는지(서버의 ForecastPeriod와 같은 경계). */
function inRange(date: string, query: ForecastQuery): boolean {
  if (query.month === undefined) return inPeriod(date, query.year, query.quarter)
  const { year } = periodOf(date)
  return year === query.year && Number(date.slice(5, 7)) === query.month
}

function summarize(ctx: MockContext, query: ForecastQuery): ForecastSummary {
  if (query.quarter !== undefined && query.month !== undefined) throw validation(QUARTER_MONTH_EXCLUSIVE)
  const { data } = ctx.store
  const forecasts = codeSetOf(ctx).forecasts.filter((c) => c.outcome !== 'lost')
  const columns: ForecastColumn[] = forecasts.map((c) => ({
    key: c.key,
    name: c.name,
    outcome: c.outcome === 'won' ? 'won' : 'open',
    order: c.order,
  }))
  const openKeys = new Set(columns.filter((c) => c.outcome === 'open').map((c) => c.key))
  const blank = (ownerId: number | null, ownerName: string): ForecastSummaryRow => ({
    ownerId,
    ownerName,
    cells: Object.fromEntries(columns.map((c) => [c.key, emptyCell()])),
    total: emptyCell(),
  })

  const deals = data.deals.filter(
    (d) =>
      inRange(d.revenueDate, query) &&
      (query.vendorId ? d.vendorId === query.vendorId : true) &&
      (query.ownerId ? d.ownerId === query.ownerId : true),
  )
  const totalRow = blank(null, '합계')
  const byOwner = new Map<number, { ref: UserRef; row: ForecastSummaryRow }>()
  for (const deal of deals) {
    const cell = totalRow.cells[deal.forecastKey]
    if (!cell) continue // Lost 등 열에 없는 Forecast는 합계에서 제외
    const ref = userRef(data, deal.ownerId)
    const entry = byOwner.get(ref.id) ?? { ref, row: blank(ref.id, userLabel(ref)) }
    byOwner.set(ref.id, entry)
    for (const target of [entry.row, totalRow]) {
      const targetCell = target.cells[deal.forecastKey]
      if (targetCell) add(targetCell, deal)
      if (openKeys.has(deal.forecastKey)) add(target.total, deal)
    }
  }
  const rows = orderedRows([...byOwner.values()])
  return { query: { ...query }, columns, rows, totalRow, basis: 'live', asOf: ctx.clock.now(), snapshotPeriod: null }
}

export function createForecastGateway(ctx: MockContext): ForecastGateway {
  return {
    summary: (query) =>
      read(ctx, () => {
        requireUser(ctx)
        return summarize(ctx, query)
      }),
    snapshots: () => read(ctx, () => listSnapshots(ctx)),
    snapshotSummary: (period, query) => read(ctx, () => snapshotSummary(ctx, period, query)),
  }
}
