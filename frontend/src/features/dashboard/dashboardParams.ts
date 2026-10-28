import { parseId } from '../../shared/model/ids'
import type { Quarter } from '../../shared/model/period'
import { effectiveQuarters, parseQuarterParam, quarterParam } from '../../shared/model/quarterSet'
import type { DashboardQuery } from '../../shared/model/types'

export type DashboardTab = 'status' | 'forecast'

/** 탭 하나의 검색 조건. */
export interface TabFilters {
  year: number
  /** 고른 분기(누른 그대로, 넷 다 포함). 조회·Drill-down에서만 effectiveQuarters로 정규화한다. */
  quarters: Quarter[]
  ownerId?: number
  /** Vendor id. */
  vendor?: number
}

/**
 * 화면 필터 상태. URL 쿼리 `tab`과 `<탭>.year|quarter|owner|vendor`(탭: status, forecast)와 1:1로 대응한다.
 * 탭마다 조건이 따로이고, 조회·Drill-down은 활성 탭 조건만 쓴다.
 */
export interface DashboardFilters {
  tab: DashboardTab
  status: TabFilters
  forecast: TabFilters
}

/** 서버가 받는 연도 하한(1900)과 같다. 4자리 숫자만 받는다. */
const MIN_YEAR = 1900

function parseTab(raw: string | null): DashboardTab {
  return raw === 'forecast' ? 'forecast' : 'status'
}

function parseYear(raw: string | null, fallback: number): number {
  const year = raw !== null && /^\d{4}$/.test(raw) ? Number(raw) : NaN
  return Number.isInteger(year) && year >= MIN_YEAR ? year : fallback
}

/** `<탭>.<키>`가 있으면 그 값(틀려도 정본), 없으면 예전 접두사 없는 키(하위 호환). */
function rawOf(params: URLSearchParams, prefix: DashboardTab, key: string, legacy: boolean): string | null {
  const own = params.get(`${prefix}.${key}`)
  if (own !== null) return own
  return legacy ? params.get(key) : null
}

/** 예전 주소: 접두사 없는 year·owner·vendor는 두 탭 모두, quarter는 Status 탭만(예전 Forecast 탭은 Quarter를 쓰지 않았다). */
function tabFrom(params: URLSearchParams, prefix: DashboardTab, thisYear: number): TabFilters {
  const tab: TabFilters = {
    year: parseYear(rawOf(params, prefix, 'year', true), thisYear),
    quarters: parseQuarterParam(rawOf(params, prefix, 'quarter', prefix === 'status')),
  }
  const ownerId = parseId(rawOf(params, prefix, 'owner', true))
  if (ownerId !== undefined) tab.ownerId = ownerId
  const vendor = parseId(rawOf(params, prefix, 'vendor', true))
  if (vendor !== undefined) tab.vendor = vendor
  return tab
}

/** URL 쿼리 → 필터. `thisYear`는 year가 없을 때 쓰는 기본 연도(올해). `sq`와 다른 화면의 키는 읽지 않는다. */
export function filtersFromParams(params: URLSearchParams, thisYear: number): DashboardFilters {
  return { tab: parseTab(params.get('tab')), status: tabFrom(params, 'status', thisYear), forecast: tabFrom(params, 'forecast', thisYear) }
}

function writeTab(params: URLSearchParams, prefix: DashboardTab, tab: TabFilters): void {
  params.set(`${prefix}.year`, String(tab.year))
  const quarters = quarterParam(tab.quarters)
  if (quarters) params.set(`${prefix}.quarter`, quarters)
  if (tab.ownerId) params.set(`${prefix}.owner`, String(tab.ownerId))
  if (tab.vendor) params.set(`${prefix}.vendor`, String(tab.vendor))
}

/** 기본값이어도 tab과 두 탭의 year는 항상 URL에 남긴다. 빈 값은 키를 만들지 않고 접두사 없는 예전 키는 쓰지 않는다. */
export function paramsFromFilters(filters: DashboardFilters): URLSearchParams {
  const params = new URLSearchParams()
  params.set('tab', filters.tab)
  writeTab(params, 'status', filters.status)
  writeTab(params, 'forecast', filters.forecast)
  return params
}

/** 활성 탭 조건. */
export function activeFilters(filters: DashboardFilters): TabFilters {
  return filters[filters.tab]
}

/** 활성 탭 조건만 patch한 사본(다른 탭은 그대로). */
export function patchActive(filters: DashboardFilters, patch: Partial<TabFilters>): DashboardFilters {
  return { ...filters, [filters.tab]: { ...filters[filters.tab], ...patch } }
}

/** 요약 조회 조건: 탭 하나의 조건. 분기는 정규화해(없음·넷 다 = 생략) 보낸다. */
export function queryOf(tab: TabFilters): DashboardQuery {
  const query: DashboardQuery = { year: tab.year }
  const quarters = effectiveQuarters(tab.quarters)
  if (quarters.length > 0) query.quarters = quarters
  if (tab.ownerId) query.ownerId = tab.ownerId
  if (tab.vendor) query.vendorId = tab.vendor
  return query
}
