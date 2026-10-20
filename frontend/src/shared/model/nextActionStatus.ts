import type { NextActionStatus, NextActionStatusFilter } from './types'

/** 화면 라벨(서버 `NextActionStatus.label`과 같다). */
export const NEXT_ACTION_STATUS_LABEL: Record<NextActionStatus, string> = {
  open: 'Open',
  done: '종료(수행)',
  notDone: '종료(미수행)',
}

/** 상태 필터 선택지(첫 항목은 필터 없음). */
export const NEXT_ACTION_STATUS_FILTER_OPTIONS: readonly { value: NextActionStatusFilter | ''; label: string }[] = [
  { value: '', label: '전체' },
  { value: 'open', label: 'Open' },
  { value: 'done', label: '종료(수행)' },
  { value: 'notDone', label: '종료(미수행)' },
  { value: 'closed', label: '종료(전체)' },
]

/** URL(`next_status`) 값 ↔ 필터. URL은 서버 쿼리 값(`not_done`)을 그대로 쓴다. 모르는 값은 null. */
const PARAM_TO_FILTER: Record<string, NextActionStatusFilter> = {
  open: 'open',
  done: 'done',
  not_done: 'notDone',
  closed: 'closed',
}

export function nextActionStatusFromParam(value: string | null): NextActionStatusFilter | null {
  return value !== null && Object.hasOwn(PARAM_TO_FILTER, value) ? (PARAM_TO_FILTER[value] ?? null) : null
}

export function nextActionStatusToParam(filter: NextActionStatusFilter): string {
  return filter === 'notDone' ? 'not_done' : filter
}

const FILTER_VALUES: readonly string[] = ['open', 'done', 'notDone', 'closed']

export function isNextActionStatusFilter(value: string): value is NextActionStatusFilter {
  return FILTER_VALUES.includes(value)
}
