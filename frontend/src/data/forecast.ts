import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { ForecastQuery, ForecastSnapshotInfo, ForecastSummary } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, type Query } from './result'

/**
 * gateway.forecast.summary(query). 키 keys.forecastSummary(query).
 * 담당자별 Deal 목록은 useDeals({ ownerId, year, quarter, ...})를 쓴다(별도 forecast API 없음).
 * Deal/Code/User 변경 훅이 keys.forecast를 무효화한다.
 * 필터가 바뀌는 동안 이전 요약을 유지한다(`keepPreviousData`).
 */
export function useForecastSummary(query: ForecastQuery, enabled = true): Query<ForecastSummary> {
  return useQuery<ForecastSummary, ApiError>({
    queryKey: keys.forecastSummary(query),
    queryFn: () => gateway.forecast.summary(query),
    enabled,
    placeholderData: keepPreviousData,
    ...NO_RETRY,
  })
}

/** 저장된 월말 스냅숏 목록(기준 시점 선택지). */
export function useForecastSnapshots(): Query<ForecastSnapshotInfo[]> {
  return useQuery<ForecastSnapshotInfo[], ApiError>({
    queryKey: keys.forecastSnapshots,
    queryFn: () => gateway.forecast.snapshots(),
    ...NO_RETRY,
  })
}

/** 월말 스냅숏 기준 요약. period가 없으면 조회하지 않는다. Vendor 조건은 받지 않는다. */
export function useForecastSnapshotSummary(period: string | undefined, query: Omit<ForecastQuery, 'vendorId'>): Query<ForecastSummary> {
  return useQuery<ForecastSummary, ApiError>({
    queryKey: keys.forecastSnapshotSummary(period ?? '', query),
    queryFn: () => gateway.forecast.snapshotSummary(period ?? '', query),
    enabled: period !== undefined,
    placeholderData: keepPreviousData,
    ...NO_RETRY,
  })
}
