import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { AlertSettings } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.alerts.get. 키 keys.alerts. 로그인한 모든 역할이 읽는다(목록 범례 등). */
export function useAlertSettings(): Query<AlertSettings> {
  return useQuery<AlertSettings, ApiError>({
    queryKey: keys.alerts,
    queryFn: () => gateway.alerts.get(),
    ...NO_RETRY,
  })
}

/** gateway.alerts.save(staleDays). 성공: Risk가 바뀌므로 Deal 목록·상세(keys.deals)와 keys.alerts, Dashboard 주의 타일(keys.dashboard) 무효화. */
export function useSaveAlertSettings(): Mutation<number, AlertSettings> {
  const invalidate = useInvalidate()
  return useMutation<AlertSettings, ApiError, number>({
    mutationFn: (staleDays) => gateway.alerts.save(staleDays),
    onSuccess: () => invalidate(keys.alerts, keys.deals, keys.dashboard),
  })
}
