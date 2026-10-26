import { forecastParam } from '../../shared/model/forecastKeys'
import type { ForecastColumn } from '../../shared/model/types'

/**
 * Drill-down: Dashboard의 숫자를 눌렀을 때 여는 Deal 목록 주소. 목록의 조건은 이 주소의 쿼리가 전부다(이전 정렬·페이지는 이어받지 않는다).
 * 모든 주소는 여기서만 만든다. Lost 제외·Open 숫자는 응답 `forecast.columns`로 만든 Forecast key 집합을 `forecast`에 실어
 * 목록 건수가 누른 숫자와 같다(2026-10-26). 집합이 비면(예: Open 코드가 없음) 주소를 만들지 않고 null을 돌려준다.
 * 서버 정의(`DashboardCriteria`)와의 대응: Open 합계·이번 분기/달 Expected Close = Open 집합, Status·분기 합계 = Lost 제외 집합.
 * 키 순서는 year, quarter, month, owner, vendor, status, forecast, overdue, stale로 고정한다.
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
  forecast?: readonly string[]
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
  if (c.forecast !== undefined) params.set('forecast', forecastParam(c.forecast))
  if (c.flag !== undefined) params.set(c.flag, '1')
  return `/deals?${params.toString()}`
}

/** Drill-down에 싣는 Forecast 집합(정렬된 key). */
export interface ForecastSets {
  /** outcome이 open인 열. */
  open: readonly string[]
  /** outcome이 lost가 아닌 열(open + won). */
  notLost: readonly string[]
}

/** Dashboard 응답 `forecast.columns`(Lost 제외)로 만든다. 혹시 lost 열이 있어도 뺀다. */
export function forecastSetsOf(columns: readonly ForecastColumn[]): ForecastSets {
  const keys = (pick: (outcome: string) => boolean) => columns.filter((c) => pick(c.outcome)).map((c) => c.key).sort()
  return { open: keys((o) => o === 'open'), notLost: keys((o) => o !== 'lost') }
}

/** 집합이 비면 null(조건 없는 목록으로 가면 건수가 달라진다). */
const withSet = (set: readonly string[], condition: Condition): string | null => (set.length > 0 ? pathOf({ ...condition, forecast: set }) : null)

/** 담당자·Vendor만 이어받는다(기간은 가져가지 않는다). */
const who = (scope: DashboardScope): Pick<Condition, 'ownerId' | 'vendor'> => ({ ownerId: scope.ownerId, vendor: scope.vendor })

/** Forecast 타일: 선택한 기간·담당자·Vendor + Forecast 코드. */
export const forecastTilePath = (scope: DashboardScope, forecastKey: string): string => pathOf({ ...scope, forecast: [forecastKey] })

/** Open 합계 타일: Open 코드 전부. */
export const openTotalPath = (scope: DashboardScope, sets: ForecastSets): string | null => withSet(sets.open, { ...scope })

/** Status 막대·표 행: 그 Status + Lost 제외 코드 전부. */
export const statusPath = (scope: DashboardScope, statusKey: string, sets: ForecastSets): string | null =>
  withSet(sets.notLost, { ...scope, status: statusKey })

/** Status 표 합계 행: Lost 제외 코드 전부. */
export const statusTotalPath = (scope: DashboardScope, sets: ForecastSets): string | null => withSet(sets.notLost, { ...scope })

/** 기한초과 타일: 기간은 적용하지 않는다. */
export const overduePath = (scope: DashboardScope): string => pathOf({ ...who(scope), flag: 'overdue' })

/** 미업데이트 타일: 기간은 적용하지 않는다. */
export const stalePath = (scope: DashboardScope): string => pathOf({ ...who(scope), flag: 'stale' })

/** 이번 분기 Expected Close: 연·분기는 서버가 알려준 오늘 기준 값이다. */
export const closingQuarterPath = (scope: DashboardScope, thisQuarter: { year: number; quarter: number }, sets: ForecastSets): string | null =>
  withSet(sets.open, { year: thisQuarter.year, quarter: thisQuarter.quarter, ...who(scope) })

/** 이번 달 Expected Close: 연·월은 서버가 알려준 오늘 기준 값이다. */
export const closingMonthPath = (scope: DashboardScope, thisMonth: { year: number; month: number }, sets: ForecastSets): string | null =>
  withSet(sets.open, { year: thisMonth.year, month: thisMonth.month, ...who(scope) })

/** 분기 막대 조각·표 셀: 그 분기와 Forecast 코드(선택한 Quarter는 따르지 않는다). */
export const quarterCellPath = (scope: DashboardScope, quarter: number, forecastKey: string): string =>
  pathOf({ year: scope.year, quarter, ...who(scope), forecast: [forecastKey] })

/** 분기 표 합계: 그 분기 + Lost 제외 코드 전부. */
export const quarterTotalPath = (scope: DashboardScope, quarter: number, sets: ForecastSets): string | null =>
  withSet(sets.notLost, { year: scope.year, quarter, ...who(scope) })
