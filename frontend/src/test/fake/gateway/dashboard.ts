import type { DashboardGateway } from '../../../gateway/types'
import { periodOf, type Quarter } from '../../../shared/model/period'
import type {
  DashboardQuarter,
  DashboardQuery,
  DashboardSummary,
  Deal,
  ForecastCell,
  ForecastColumn,
} from '../../../shared/model/types'
import { validation } from '../errors'
import { read, requireUser, type MockContext } from './context'
import { codeSetOf } from './dealChange'
import { dealRow } from './views'

const YEAR_MIN = 1900
const YEAR_MAX = 9999
const QUARTER_FIRST_MONTH: Record<Quarter, number> = { 1: 1, 2: 4, 3: 7, 4: 10 }
const QUARTER_LAST_DAY: Record<Quarter, string> = { 1: '03-31', 2: '06-30', 3: '09-30', 4: '12-31' }

const zero = (): ForecastCell => ({ count: 0, amount: 0 })

function add(cell: ForecastCell, deal: Deal): void {
  cell.count += 1
  cell.amount += deal.revenueAmount
}

function sumOf(cells: ForecastCell[]): ForecastCell {
  return cells.reduce((sum, c) => ({ count: sum.count + c.count, amount: sum.amount + c.amount }), zero())
}

function quarterRange(year: number, quarter: Quarter): { from: string; to: string } {
  const month = String(QUARTER_FIRST_MONTH[quarter]).padStart(2, '0')
  return { from: `${year}-${month}-01`, to: `${year}-${QUARTER_LAST_DAY[quarter]}` }
}

/**
 * 서버(`GetDashboardSummary`)와 같은 규칙을 Fake 시드에서 직접 계산한다. Deal 목록 필터(`listDeals`)를 부르지 않고
 * Deal을 직접 훑어서, Drill-down 조건과 일치하는지를 계약 테스트가 따로 확인할 수 있다.
 * - Forecast 타일: 기간·담당자·Vendor, Lost 제외
 * - Status: 같은 조건 + Forecast가 Lost가 아닌 Deal
 * - 분기: 연도·담당자·Vendor(Quarter 무시), 항상 Q1~Q4
 * - 주의: 담당자·Vendor만(기간 무시). 이번 달·분기 Expected Close는 Open Deal만, 기준은 Fake 시계의 업무 날짜
 */
function summarize(ctx: MockContext, query: DashboardQuery): DashboardSummary {
  if (!Number.isInteger(query.year) || query.year < YEAR_MIN || query.year > YEAR_MAX) {
    throw validation(`연도는 ${YEAR_MIN}~${YEAR_MAX} 중에서 입력하세요.`)
  }
  if (query.quarter !== undefined && ![1, 2, 3, 4].includes(query.quarter)) throw validation('분기는 1~4 중에서 선택하세요.')
  const { data } = ctx.store
  const codes = codeSetOf(ctx)
  const outcomeOf = new Map(codes.forecasts.map((c) => [c.key, c.outcome]))
  const columns: ForecastColumn[] = codes.forecasts
    .filter((c) => c.outcome !== 'lost')
    .map((c) => ({ key: c.key, name: c.name, outcome: c.outcome === 'won' ? 'won' : 'open', order: c.order }))
  const openKeys = columns.filter((c) => c.outcome === 'open').map((c) => c.key)
  const blank = () => Object.fromEntries(columns.map((c) => [c.key, zero()])) as Record<string, ForecastCell>

  const scoped = data.deals.filter(
    (d) => (query.ownerId ? d.ownerId === query.ownerId : true) && (query.vendorId ? d.vendorId === query.vendorId : true),
  )
  const inYear = scoped.filter((d) => periodOf(d.revenueDate).year === query.year)
  const inPeriod = inYear.filter((d) => query.quarter === undefined || periodOf(d.revenueDate).quarter === query.quarter)

  const cells = blank()
  for (const deal of inPeriod) {
    const cell = cells[deal.forecastKey]
    if (cell) add(cell, deal)
  }

  const statuses = codes.statuses.map((c) => ({ key: c.key, name: c.name, order: c.order, ...zero() }))
  for (const deal of inPeriod) {
    if (outcomeOf.get(deal.forecastKey) === 'lost') continue
    const item = statuses.find((s) => s.key === deal.statusKey)
    if (item) add(item, deal)
  }

  const quarters: DashboardQuarter[] = ([1, 2, 3, 4] as const).map((q) => {
    const quarterCells = blank()
    for (const deal of inYear) {
      const cell = quarterCells[deal.forecastKey]
      if (cell && periodOf(deal.revenueDate).quarter === q) add(cell, deal)
    }
    const openTotal = sumOf(openKeys.map((k) => quarterCells[k] as ForecastCell))
    const wonTotal = sumOf(columns.filter((c) => c.outcome === 'won').map((c) => quarterCells[c.key] as ForecastCell))
    return { quarter: q, ...quarterRange(query.year, q), cells: quarterCells, openTotal, total: sumOf([openTotal, wonTotal]) }
  })

  const today = ctx.clock.today()
  const todayPeriod = periodOf(today)
  const todayMonth = Number(today.slice(5, 7))
  const isOpen = (d: Deal) => outcomeOf.get(d.forecastKey) === 'open'
  const risk = (d: Deal) => dealRow(ctx, d).risk
  return {
    asOf: ctx.clock.now(),
    today,
    period: {
      year: query.year,
      quarter: query.quarter ?? null,
      ...(query.quarter === undefined ? { from: `${query.year}-01-01`, to: `${query.year}-12-31` } : quarterRange(query.year, query.quarter)),
    },
    forecast: { columns, cells, openTotal: sumOf(openKeys.map((k) => cells[k] as ForecastCell)) },
    statuses: { items: statuses, total: sumOf(statuses) },
    quarters,
    attention: {
      staleDays: data.alerts.staleDays,
      overdue: scoped.filter((d) => ['overdue', 'overdue_stale'].includes(risk(d) ?? '')).length,
      stale: scoped.filter((d) => ['stale', 'overdue_stale'].includes(risk(d) ?? '')).length,
      closingThisMonth: {
        year: todayPeriod.year,
        month: todayMonth,
        count: scoped.filter((d) => isOpen(d) && d.revenueDate.slice(0, 7) === today.slice(0, 7)).length,
      },
      closingThisQuarter: {
        year: todayPeriod.year,
        quarter: todayPeriod.quarter,
        count: scoped.filter((d) => isOpen(d) && periodOf(d.revenueDate).year === todayPeriod.year && periodOf(d.revenueDate).quarter === todayPeriod.quarter).length,
      },
    },
  }
}

export function createDashboardGateway(ctx: MockContext): DashboardGateway {
  return {
    summary: (query) =>
      read(ctx, () => {
        requireUser(ctx)
        return summarize(ctx, query)
      }),
  }
}
