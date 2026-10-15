import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { ForecastQuery, ForecastSummary } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, type Query } from './result'

/**
 * gateway.forecast.summary(query). 키 keys.forecastSummary(query).
 * 담당자별 Deal 목록은 useDeals({ ownerId, year, quarter, ...})를 쓴다(별도 forecast API 없음).
 * Deal/Code/User 변경 훅이 keys.forecast를 무효화한다.
 * 필터가 바뀌는 동안 이전 요약을 유지한다(`keepPreviousData`).
 */
export function useForecastSummary(query: ForecastQuery): Query<ForecastSummary> {
  return useQuery<ForecastSummary, ApiError>({
    queryKey: keys.forecastSummary(query),
    queryFn: () => gateway.forecast.summary(query),
    placeholderData: keepPreviousData,
    ...NO_RETRY,
  })
}
