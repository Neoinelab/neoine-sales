import { BANT_CATEGORIES, DEAL_PAGE_SIZE, type BantCategory } from '../../../shared/model/constants'
import type { DealListQuery, DealSortKey, SortOrder } from '../../../shared/model/types'

import { nextActionStatusFromParam } from '../../../shared/model/nextActionStatus'
import { FILTER_KEYS } from '../../../shared/model/dealListMemory'

/** URL 쿼리 키(정의는 shared의 기억 모듈에 있고 여기서 다시 내보낸다). */
export { FILTER_KEYS }

const SORT_KEYS: readonly DealSortKey[] = ['name', 'revenueAmount', 'revenueDate', 'lastUpdatedAt', 'statusKey']

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
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

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
    ['owner', 'ownerId'],
    ['status', 'statusKey'],
    ['forecast', 'forecastKey'],
    ['from', 'revenueFrom'],
    ['to', 'revenueTo'],
  ] as const
  for (const [param, field] of pairs) {
    const value = text(param)
    if (value) query[field] = value
  }

  // Vendor·Solution은 id(UUID)만 받는다. 예전 이름 기반 URL 값은 무시한다.
  const vendorId = text('vendor')
  if (vendorId && UUID.test(vendorId)) query.vendorId = vendorId
  const solutionId = text('solution')
  if (solutionId && UUID.test(solutionId)) query.solutionId = solutionId

  const year = positiveInt(params.get('year'))
  if (year !== null) query.year = year
  // 분기는 연도와 따로 보낸다(연도 없이 분기만 있으면 서버가 올해로 본다).
  const quarter = Number(params.get('quarter'))
  if (quarter === 1 || quarter === 2 || quarter === 3 || quarter === 4) query.quarter = quarter

  const bant: Partial<Record<BantCategory, string>> = {}
  for (const category of BANT_CATEGORIES) {
    const id = text(category)
    if (id) bant[category] = id
  }
  if (Object.keys(bant).length > 0) query.bantLabelIds = bant
  if (params.get('mine') === '1') query.mine = true
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
