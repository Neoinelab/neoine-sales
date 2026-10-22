import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { DashboardQuery, DashboardSummary } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, type Query } from './result'

/**
 * gateway.dashboard.summary(query). 키 keys.dashboardSummary(query).
 * Status·Forecast 두 탭이 같은 조회 훅을 쓰며, Quarter는 Status 탭에만 적용되어 Quarter를 고르면 두 탭의 요청(키)이 다르다. keys.forecast(Deal·Code·User·Action 변경 훅)와 경고 기준 저장이 무효화한다.
 * 필터가 바뀌는 동안 이전 요약을 유지한다(`keepPreviousData`).
 */
export function useDashboardSummary(query: DashboardQuery): Query<DashboardSummary> {
  return useQuery<DashboardSummary, ApiError>({
    queryKey: keys.dashboardSummary(query),
    queryFn: () => gateway.dashboard.summary(query),
    placeholderData: keepPreviousData,
    ...NO_RETRY,
  })
}
