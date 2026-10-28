import type { Quarter } from '../../../shared/model/period'
import { DEAL_PAGE_SIZE, SOLUTION_MAX_LENGTH } from '../../../shared/model/constants'
import type { DealListQuery, DealSortKey, SortOrder } from '../../../shared/model/types'

import { nextActionStatusFromParam } from '../../../shared/model/nextActionStatus'
import { parseId } from '../../../shared/model/ids'
import { parseMonth } from '../../../shared/model/month'
import { effectiveQuarters, monthsOfQuarters, parseQuarterParam, quarterParam, toggleQuarter } from '../../../shared/model/quarterSet'
import { isCalendarDate } from '../../../shared/model/updatedPeriod'
import { FILTER_KEYS } from '../../../shared/model/dealListMemory'
import { parseForecastParam } from '../../../shared/model/forecastKeys'

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

function isSortKey(value: string | null): value is DealSortKey {
  return SORT_KEYS.some((key) => key === value)
}

/** URL의 분기 목록(오름차순, 중복 제거, 형식이 틀린 항목은 버림). 넷 다여도 누른 그대로다. */
export function quartersOf(params: URLSearchParams): Quarter[] {
  return parseQuarterParam(params.get('quarter'))
}

/** 월 선택지: 고른 분기들의 월 합집합, 분기가 없거나 넷 다면 12달. */
export function monthOptions(params: URLSearchParams): readonly number[] {
  return monthsOfQuarters(quartersOf(params))
}

/** 화면과 질의가 쓰는 월: 월 선택지에 있는 월만, 아니면 undefined. */
export function effectiveMonth(params: URLSearchParams): number | undefined {
  const month = parseMonth(params.get('month'))
  return month !== undefined && monthOptions(params).includes(month) ? month : undefined
}

/** 분기 목록을 바꿀 때의 URL 변경. 보이던 월이 새 선택지에 없거나, 지금 선택지 밖이라 숨어 있던 월이면 월을 지운다(숨은 월이 되살아나지 않게). */
function quarterPatch(params: URLSearchParams, next: readonly Quarter[]): Record<string, string> {
  const raw = params.get('month')
  const month = effectiveMonth(params)
  const patch = { quarter: quarterParam(next) }
  const hidden = raw !== null && raw !== '' && month === undefined
  return hidden || (month !== undefined && !monthsOfQuarters(next).includes(month)) ? { ...patch, month: '' } : patch
}

/** 분기 하나를 켜거나 끌 때 URL에 적용할 변경. */
export function quarterTogglePatch(params: URLSearchParams, quarter: Quarter, on: boolean): Record<string, string> {
  return quarterPatch(params, toggleQuarter(quartersOf(params), quarter, on))
}

/** "전체"(선택 해제): 보이던 월은 남기고, 보이지 않던 월(선택지 밖)은 지운다. */
export function quarterClearPatch(params: URLSearchParams): Record<string, string> {
  return effectiveMonth(params) !== undefined ? { quarter: '' } : { quarter: '', month: '' }
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
  const status = text('status')
  if (status) query.statusKey = status
  const forecastKeys = parseForecastParam(params.get('forecast'))
  if (forecastKeys.length > 0) query.forecastKeys = forecastKeys
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
  // 월은 분기와 함께 보내지 않는다(서버 422). 월 선택지에 있는 월이면 월만, 아니면 정규화한 분기 목록(넷 다면 생략)만 보낸다.
  const quarters = effectiveQuarters(quartersOf(params))
  const month = effectiveMonth(params)
  if (month !== undefined) query.month = month
  else if (quarters.length > 0) query.quarters = quarters

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

/** 정렬·페이지를 뺀 조건이 하나라도 있으면 true. 연도 '전체'(`year=all`)는 조건이 아니다(빈 상태 문구 구분). */
export function hasActiveFilter(params: URLSearchParams): boolean {
  return FILTER_KEYS.some((key) => {
    const value = (params.get(key) ?? '').trim()
    return value !== '' && !(key === 'year' && value === 'all')
  })
}

/** 필터 키가 하나라도 값을 가지면 true(`year=all` 포함). false면 목록은 기본 조건을 적용한다. */
export function hasListCondition(params: URLSearchParams): boolean {
  return FILTER_KEYS.some((key) => (params.get(key) ?? '').trim() !== '')
}

/** 조건 없이 들어온 목록의 기본 조건: 올해만(Quarter 전체). 정렬은 이어받고 페이지·모르는 키는 버린다. today는 'YYYY-MM-DD'. */
export function defaultListParams(today: string, current?: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams({ year: today.slice(0, 4) })
  for (const key of ['sort', 'order']) {
    const value = current?.get(key)
    if (value) next.set(key, value)
  }
  return next
}
