import { useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { HistoryEntry, HistoryQuery } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, type Query } from './result'

/** gateway.history.list(dealCode, query). 키 keys.historyList. dealCode가 undefined면 비활성(enabled=false). */
export function useHistory(dealCode: string | undefined, query: HistoryQuery = {}): Query<HistoryEntry[]> {
  return useQuery<HistoryEntry[], ApiError>({
    queryKey: keys.historyList(dealCode ?? '', query),
    queryFn: () => gateway.history.list(dealCode ?? '', query),
    enabled: dealCode !== undefined,
    ...NO_RETRY,
  })
}
