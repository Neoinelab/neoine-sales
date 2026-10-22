import { parseId } from '../../shared/model/ids'
import type { DashboardQuery } from '../../shared/model/types'

export type DashboardTab = 'status' | 'forecast'

/** 화면 필터 상태. URL 쿼리(`tab`, `year`, `quarter`, `sq`, `owner`, `vendor`)와 1:1로 대응한다. Quarter는 Status 탭에만 적용된다. */
export interface DashboardFilters {
  tab: DashboardTab
  year: number
  quarter?: 1 | 2 | 3 | 4
  /** Forecast 탭 하단 Selected Quarter(URL `sq`). 서버 조회 조건이 아니다. */
  selectedQuarter?: 1 | 2 | 3 | 4
  ownerId?: number
  /** Vendor id(URL `vendor=<id>`). */
  vendor?: number
}

/** 서버가 받는 연도 하한(1900)과 같다. 4자리 숫자만 받는다. */
const MIN_YEAR = 1900

function parseTab(raw: string | null): DashboardTab {
  return raw === 'forecast' ? 'forecast' : 'status'
}

function parseQuarter(raw: string | null): 1 | 2 | 3 | 4 | undefined {
  return raw === '1' || raw === '2' || raw === '3' || raw === '4' ? (Number(raw) as 1 | 2 | 3 | 4) : undefined
}

function parseYear(raw: string | null, fallback: number): number {
  const year = raw !== null && /^\d{4}$/.test(raw) ? Number(raw) : NaN
  return Number.isInteger(year) && year >= MIN_YEAR ? year : fallback
}

/** URL 쿼리 → 필터. `thisYear`는 URL에 year가 없을 때 쓰는 기본 연도(올해, `useToday().year`). 다른 화면의 키(month·snap·sel)는 읽지 않는다. */
export function filtersFromParams(params: URLSearchParams, thisYear: number): DashboardFilters {
  const filters: DashboardFilters = { tab: parseTab(params.get('tab')), year: parseYear(params.get('year'), thisYear) }
  const quarter = parseQuarter(params.get('quarter'))
  if (quarter) filters.quarter = quarter
  const selectedQuarter = parseQuarter(params.get('sq'))
  if (selectedQuarter) filters.selectedQuarter = selectedQuarter
  const ownerId = parseId(params.get('owner'))
  if (ownerId !== undefined) filters.ownerId = ownerId
  const vendor = parseId(params.get('vendor'))
  if (vendor !== undefined) filters.vendor = vendor
  return filters
}

/** 기본값이어도 tab과 year는 항상 URL에 남긴다. 빈 값은 키를 만들지 않는다. */
export function paramsFromFilters(filters: DashboardFilters): URLSearchParams {
  const params = new URLSearchParams()
  params.set('tab', filters.tab)
  params.set('year', String(filters.year))
  if (filters.quarter) params.set('quarter', String(filters.quarter))
  if (filters.selectedQuarter) params.set('sq', String(filters.selectedQuarter))
  if (filters.ownerId) params.set('owner', String(filters.ownerId))
  if (filters.vendor) params.set('vendor', String(filters.vendor))
  return params
}

/** 요약 조회 조건. Forecast 탭은 Quarter 필터를 쓰지 않으므로 quarter를 보내지 않는다(연간 값 + 4분기 전체). `selectedQuarter`는 보내지 않는다. */
export function queryOf(filters: DashboardFilters): DashboardQuery {
  const query: DashboardQuery = { year: filters.year }
  if (filters.quarter && filters.tab !== 'forecast') query.quarter = filters.quarter
  if (filters.ownerId) query.ownerId = filters.ownerId
  if (filters.vendor) query.vendorId = filters.vendor
  return query
}

/** Forecast 탭 하단에서 선택된 분기. 명시 값 우선, 없으면 선택 연도가 올해일 때 오늘이 속한 분기, 아니면 Q1. */
export function selectedQuarterOf(filters: DashboardFilters, today: string): 1 | 2 | 3 | 4 {
  if (filters.selectedQuarter) return filters.selectedQuarter
  if (filters.year !== Number(today.slice(0, 4))) return 1
  return (Math.floor((Number(today.slice(5, 7)) - 1) / 3) + 1) as 1 | 2 | 3 | 4
}
