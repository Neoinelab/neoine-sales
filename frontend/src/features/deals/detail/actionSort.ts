import type { ActionSortKey, SortOrder } from '../../../shared/model/types'

export interface ActionSortState {
  sort: ActionSortKey
  order: SortOrder
}

/** 처음 보이는 순서: 수행일시 최신순(서버 기본과 같다). */
export const DEFAULT_ACTION_SORT: ActionSortState = { sort: 'actedAt', order: 'desc' }

const NATURAL_ORDER: Record<ActionSortKey, SortOrder> = {
  actedAt: 'desc',
  dueDate: 'asc',
  actor: 'asc',
  type: 'asc',
  nextActionStatus: 'asc',
}

/** 같은 열을 다시 고르면 방향을 뒤집고, 다른 열이면 그 열의 자연스러운 방향으로 시작한다. */
export function nextActionSort(current: ActionSortState, key: ActionSortKey): ActionSortState {
  if (current.sort === key) return { sort: key, order: current.order === 'asc' ? 'desc' : 'asc' }
  return { sort: key, order: NATURAL_ORDER[key] }
}
