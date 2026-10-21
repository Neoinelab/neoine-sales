import { parseId } from '../../shared/model/ids'
import type { ForecastQuery } from '../../shared/model/types'

/** 화면 필터 상태. URL 쿼리(`year`, `quarter`, `owner`, `vendor`, `sel`)와 1:1로 대응한다. */
export interface ForecastFilters {
  year: number
  quarter?: 1 | 2 | 3 | 4
  ownerId?: number
  /** Vendor id(URL `vendor=<id>`). */
  vendor?: number
  /** 아래 Deal 목록을 보고 있는 담당자 id. */
  selectedId?: number
}

function parseQuarter(raw: string | null): 1 | 2 | 3 | 4 | undefined {
  return raw === '1' || raw === '2' || raw === '3' || raw === '4' ? (Number(raw) as 1 | 2 | 3 | 4) : undefined
}

function parseYear(raw: string | null, fallback: number): number {
  const year = raw !== null && /^\d{4}$/.test(raw) ? Number(raw) : NaN
  return Number.isInteger(year) ? year : fallback
}

/** URL 쿼리 → 필터. `thisYear`는 URL에 year가 없을 때 쓰는 기본 연도(올해, `useToday().year`). */
export function filtersFromParams(params: URLSearchParams, thisYear: number): ForecastFilters {
  return {
    year: parseYear(params.get('year'), thisYear),
    quarter: parseQuarter(params.get('quarter')),
    ownerId: parseId(params.get('owner')),
    vendor: parseId(params.get('vendor')),
    selectedId: parseId(params.get('sel')),
  }
}

/** 기본값(올해, 전체)이어도 year는 항상 URL에 남긴다. 빈 값은 키를 만들지 않는다. */
export function paramsFromFilters(filters: ForecastFilters): URLSearchParams {
  const params = new URLSearchParams()
  params.set('year', String(filters.year))
  if (filters.quarter) params.set('quarter', String(filters.quarter))
  if (filters.ownerId) params.set('owner', String(filters.ownerId))
  if (filters.vendor) params.set('vendor', String(filters.vendor))
  if (filters.selectedId) params.set('sel', String(filters.selectedId))
  return params
}

/** 선택(`selectedId`)은 요약 조회 조건이 아니다. */
export function queryOf(filters: ForecastFilters): ForecastQuery {
  const query: ForecastQuery = { year: filters.year }
  if (filters.quarter) query.quarter = filters.quarter
  if (filters.vendor) query.vendorId = filters.vendor
  if (filters.ownerId) query.ownerId = filters.ownerId
  return query
}

/** 카드·표 제목에 쓰는 기간 이름. */
export function periodLabel(filters: Pick<ForecastFilters, 'year' | 'quarter'>): string {
  return `${filters.year} ${filters.quarter ? `Q${filters.quarter}` : '전체'}`
}
