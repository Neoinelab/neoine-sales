import { DEAL_PAGE_SIZE, SOLUTION_MAX_LENGTH } from '../../../shared/model/constants'
import type { DealListQuery, DealSortKey, ForecastOutcomeFilter, SortOrder } from '../../../shared/model/types'

import { nextActionStatusFromParam } from '../../../shared/model/nextActionStatus'
import { parseId } from '../../../shared/model/ids'
import { parseMonth } from '../../../shared/model/month'
import { isCalendarDate } from '../../../shared/model/updatedPeriod'
import { FILTER_KEYS } from '../../../shared/model/dealListMemory'

/** URL 쿼리 키(정의는 shared의 기억 모듈에 있고 여기서 다시 내보낸다). */
export { FILTER_KEYS }

const SORT_KEYS: readonly DealSortKey[] = ['name', 'revenueAmount', 'revenueDate', 'lastUpdatedAt', 'statusKey', 'owner', 'customer', 'partner', 'vendor', 'forecastKey']

export interface SortState {
  sort: DealSortKey
  order: SortOrder
}

export const DEFAULT_SORT: SortState = { sort: 'lastUpdatedAt', order: 'desc' }

/** 새 열을 처음 누를 때의 방향: 금액·최종 업데이트는 큰 값/최신부터, 나머지는 오름차순. */
const NATURAL_ORDER: Record<DealSortKey, SortOrder> = {
  name: 'asc',
  statusKey: 'asc',
  revenueDate: 'asc',
  revenueAmount: 'desc',
  lastUpdatedAt: 'desc',
  owner: 'asc',
  customer: 'asc',
  partner: 'asc',
  vendor: 'asc',
  forecastKey: 'asc',
}

/** Forecast 구분 필터의 URL 값 → 선택지. 모르는 값은 undefined('전체')다. */
export function outcomeFromParam(value: string | null): ForecastOutcomeFilter | undefined {
  return value === 'open' || value === 'won' || value === 'lost' || value === 'not_lost' ? value : undefined
}

function isSortKey(value: string | null): value is DealSortKey {
  return SORT_KEYS.some((key) => key === value)
}

function positiveInt(value: string | null): number | null {
  if (value === null || !/^\d+$/.test(value)) return null
  const parsed = Number(value)
  return parsed >= 1 ? parsed : null
}

export function currentSort(params: URLSearchParams): SortState {
  const sort = params.get('sort')
  if (!isSortKey(sort)) return DEFAULT_SORT
  const order = params.get('order')
  return { sort, order: order === 'asc' || order === 'desc' ? order : NATURAL_ORDER[sort] }
}

export function nextSort(current: SortState, key: DealSortKey): SortState {
  if (current.sort === key) return { sort: key, order: current.order === 'asc' ? 'desc' : 'asc' }
  return { sort: key, order: NATURAL_ORDER[key] }
}

export function currentPage(params: URLSearchParams): number {
  return positiveInt(params.get('page')) ?? 1
}

/** URL 쿼리 → 게이트웨이 목록 질의. 잘못된 값은 무시한다. */
export function listQueryFromParams(params: URLSearchParams): DealListQuery {
  const query: DealListQuery = { offset: (currentPage(params) - 1) * DEAL_PAGE_SIZE, limit: DEAL_PAGE_SIZE }
  const text = (key: string) => params.get(key)?.trim() || undefined

  const keyword = text('q')
  if (keyword) query.keyword = keyword
  const pairs = [
    ['status', 'statusKey'],
    ['forecast', 'forecastKey'],
  ] as const
  for (const [param, field] of pairs) {
    const value = text(param)
    if (value) query[field] = value
  }
  const outcome = outcomeFromParam(params.get('outcome'))
  if (outcome) query.forecastOutcome = outcome
  // 최종 업데이트 기간: 실제 달력 날짜만 쓰고 잘못된 값은 무시한다.
  const updatedFrom = text('updated_from')
  if (isCalendarDate(updatedFrom)) query.updatedFrom = updatedFrom
  const updatedTo = text('updated_to')
  if (isCalendarDate(updatedTo)) query.updatedTo = updatedTo

  // Owner·Vendor는 정수 id만 받는다. 예전 UUID·이름 기반 URL 값은 무시한다.
  const ownerId = parseId(params.get('owner'))
  if (ownerId !== undefined) query.ownerId = ownerId
  const vendorId = parseId(params.get('vendor'))
  if (vendorId !== undefined) query.vendorId = vendorId
  // Solution은 자유 텍스트(부분 일치)라 id로 해석하지 않고 트림한 값을 그대로 쓴다.
  const solution = text('solution')
  // 서버 한도(200자)를 넘으면 422로 목록 전체가 실패하므로 다른 잘못된 URL 값처럼 무시한다.
  if (solution && solution.length <= SOLUTION_MAX_LENGTH) query.solution = solution

  const year = positiveInt(params.get('year'))
  if (year !== null) query.year = year
  // 분기는 연도와 따로 보낸다(연도 없이 분기만 있으면 서버가 올해로 본다).
  const quarter = Number(params.get('quarter'))
  if (quarter === 1 || quarter === 2 || quarter === 3 || quarter === 4) query.quarter = quarter
  // 월은 분기와 함께 쓸 수 없다(서버 422). 둘 다 있으면 분기를 유지한다.
  const month = parseMonth(params.get('month'))
  if (query.quarter === undefined && month !== undefined) query.month = month

  if (params.get('mine') === '1') query.mine = true
  if (params.get('overdue') === '1') query.overdue = true
  if (params.get('stale') === '1') query.stale = true
  const nextStatus = nextActionStatusFromParam(params.get('next_status'))
  if (nextStatus) query.nextActionStatus = nextStatus

  if (isSortKey(params.get('sort'))) {
    const { sort, order } = currentSort(params)
    query.sort = sort
    query.order = order
  }
  return query
}

/** 조건을 바꾸면 첫 페이지로 돌아간다(`page`를 직접 바꾸는 경우만 유지). 빈 값은 지운다. */
export function updateParams(params: URLSearchParams, patch: Record<string, string | undefined>): URLSearchParams {
  const next = new URLSearchParams(params)
  for (const [key, value] of Object.entries(patch)) {
    if (value === undefined || value === '') next.delete(key)
    else next.set(key, value)
  }
  if (!('page' in patch)) next.delete('page')
  if (next.get('page') === '1') next.delete('page')
  return next
}

/** 정렬·페이지를 뺀 조건이 하나라도 있으면 true(빈 상태 문구 구분). */
export function hasActiveFilter(params: URLSearchParams): boolean {
  return FILTER_KEYS.some((key) => (params.get(key) ?? '').trim() !== '')
}
