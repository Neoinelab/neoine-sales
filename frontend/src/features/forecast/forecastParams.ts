import { parseId } from '../../shared/model/ids'
import { parseMonth } from '../../shared/model/month'
import type { ForecastQuery } from '../../shared/model/types'

/** 화면 필터 상태. URL 쿼리(`year`, `quarter`, `month`, `owner`, `vendor`, `sel`)와 1:1로 대응한다. */
export interface ForecastFilters {
  year: number
  quarter?: 1 | 2 | 3 | 4
  /** 월(1~12). quarter와 함께 쓸 수 없다(둘 다 있으면 quarter 유지). */
  month?: number
  ownerId?: number
  /** Vendor id(URL `vendor=<id>`). */
  vendor?: number
  /** 아래 Deal 목록을 보고 있는 담당자 id. */
  selectedId?: number
  /** 기준 월 스냅숏('YYYY-MM', URL `snap`). 없으면 실시간. 요약 조회 조건(`queryOf`)에는 넣지 않는다. */
  snap?: string
}

function parseQuarter(raw: string | null): 1 | 2 | 3 | 4 | undefined {
  return raw === '1' || raw === '2' || raw === '3' || raw === '4' ? (Number(raw) as 1 | 2 | 3 | 4) : undefined
}

function parseYear(raw: string | null, fallback: number): number {
  const year = raw !== null && /^\d{4}$/.test(raw) ? Number(raw) : NaN
  return Number.isInteger(year) ? year : fallback
}

function parseSnap(raw: string | null): string | undefined {
  return raw !== null && /^\d{4}-(0[1-9]|1[0-2])$/.test(raw) ? raw : undefined
}

/** URL 쿼리 → 필터. `thisYear`는 URL에 year가 없을 때 쓰는 기본 연도(올해, `useToday().year`). */
export function filtersFromParams(params: URLSearchParams, thisYear: number): ForecastFilters {
  const quarter = parseQuarter(params.get('quarter'))
  return {
    year: parseYear(params.get('year'), thisYear),
    quarter,
    month: quarter ? undefined : parseMonth(params.get('month')),
    ownerId: parseId(params.get('owner')),
    vendor: parseId(params.get('vendor')),
    selectedId: parseId(params.get('sel')),
    snap: parseSnap(params.get('snap')),
  }
}

/** 기본값(올해, 전체)이어도 year는 항상 URL에 남긴다. 빈 값은 키를 만들지 않는다. */
export function paramsFromFilters(filters: ForecastFilters): URLSearchParams {
  const params = new URLSearchParams()
  params.set('year', String(filters.year))
  if (filters.quarter) params.set('quarter', String(filters.quarter))
  else if (filters.month) params.set('month', String(filters.month))
  if (filters.ownerId) params.set('owner', String(filters.ownerId))
  if (filters.vendor) params.set('vendor', String(filters.vendor))
  if (filters.selectedId) params.set('sel', String(filters.selectedId))
  if (filters.snap) params.set('snap', filters.snap)
  return params
}

/** 선택(`selectedId`)은 요약 조회 조건이 아니다. */
export function queryOf(filters: ForecastFilters): ForecastQuery {
  const query: ForecastQuery = { year: filters.year }
  if (filters.quarter) query.quarter = filters.quarter
  else if (filters.month) query.month = filters.month
  if (filters.vendor) query.vendorId = filters.vendor
  if (filters.ownerId) query.ownerId = filters.ownerId
  return query
}

/** 카드·표 제목에 쓰는 기간 이름. */
export function periodLabel(filters: Pick<ForecastFilters, 'year' | 'quarter' | 'month'>): string {
  const part = filters.quarter ? `Q${filters.quarter}` : filters.month ? `${filters.month}월` : '전체'
  return `${filters.year} ${part}`
}
