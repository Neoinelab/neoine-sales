import type { ForecastOutcomeFilter } from '../../shared/model/types'

/**
 * Drill-down: Dashboard의 숫자를 눌렀을 때 여는 Deal 목록 주소. 목록의 조건은 이 주소의 쿼리가 전부다(이전 정렬·페이지는 이어받지 않는다).
 * 모든 주소는 여기서만 만든다(타일·표·차트가 같은 함수를 쓰므로 누른 숫자와 목록 건수가 같다).
 * 키 순서는 year, quarter, month, owner, vendor, status, forecast, outcome, overdue, stale로 고정한다.
 */

/** Dashboard 필터. Vendor는 목록에 있는 id만 넘긴다. */
export interface DashboardScope {
  year: number
  quarter?: number
  ownerId?: number
  vendor?: number
}

interface Condition {
  year?: number
  quarter?: number
  month?: number
  ownerId?: number
  vendor?: number
  status?: string
  forecast?: string
  outcome?: ForecastOutcomeFilter
  flag?: 'overdue' | 'stale'
}

function pathOf(c: Condition): string {
  const params = new URLSearchParams()
  if (c.year !== undefined) params.set('year', String(c.year))
  if (c.quarter !== undefined) params.set('quarter', String(c.quarter))
  if (c.month !== undefined) params.set('month', String(c.month))
  if (c.ownerId !== undefined) params.set('owner', String(c.ownerId))
  if (c.vendor !== undefined) params.set('vendor', String(c.vendor))
  if (c.status !== undefined) params.set('status', c.status)
  if (c.forecast !== undefined) params.set('forecast', c.forecast)
  if (c.outcome !== undefined) params.set('outcome', c.outcome)
  if (c.flag !== undefined) params.set(c.flag, '1')
  return `/deals?${params.toString()}`
}

/** 담당자·Vendor만 이어받는다(기간은 가져가지 않는다). */
const who = (scope: DashboardScope): Pick<Condition, 'ownerId' | 'vendor'> => ({ ownerId: scope.ownerId, vendor: scope.vendor })

/** Forecast 타일: 선택한 기간·담당자·Vendor + Forecast 코드. */
export const forecastTilePath = (scope: DashboardScope, forecastKey: string): string => pathOf({ ...scope, forecast: forecastKey })

/** Open 합계 타일. */
export const openTotalPath = (scope: DashboardScope): string => pathOf({ ...scope, outcome: 'open' })

/** Status 막대·표 행: Lost 제외. */
export const statusPath = (scope: DashboardScope, statusKey: string): string => pathOf({ ...scope, status: statusKey, outcome: 'not_lost' })

/** Status 표 합계 행. */
export const statusTotalPath = (scope: DashboardScope): string => pathOf({ ...scope, outcome: 'not_lost' })

/** 기한초과 타일: 기간은 적용하지 않는다. */
export const overduePath = (scope: DashboardScope): string => pathOf({ ...who(scope), flag: 'overdue' })

/** 미업데이트 타일: 기간은 적용하지 않는다. */
export const stalePath = (scope: DashboardScope): string => pathOf({ ...who(scope), flag: 'stale' })

/** 이번 분기 Expected Close(Open): 연·분기는 서버가 알려준 오늘 기준 값이다. */
export const closingQuarterPath = (scope: DashboardScope, thisQuarter: { year: number; quarter: number }): string =>
  pathOf({ year: thisQuarter.year, quarter: thisQuarter.quarter, ...who(scope), outcome: 'open' })

/** 이번 달 Expected Close(Open): 연·월은 서버가 알려준 오늘 기준 값이다. */
export const closingMonthPath = (scope: DashboardScope, thisMonth: { year: number; month: number }): string =>
  pathOf({ year: thisMonth.year, month: thisMonth.month, ...who(scope), outcome: 'open' })

/** 분기 막대 조각·표 셀: 그 분기와 Forecast 코드(선택한 Quarter는 따르지 않는다). */
export const quarterCellPath = (scope: DashboardScope, quarter: number, forecastKey: string): string =>
  pathOf({ year: scope.year, quarter, ...who(scope), forecast: forecastKey })

/** 분기 표 합계(Open + Won). */
export const quarterTotalPath = (scope: DashboardScope, quarter: number): string =>
  pathOf({ year: scope.year, quarter, ...who(scope), outcome: 'not_lost' })
