import { useQuery } from '@tanstack/react-query'
import { clock, gateway } from '../gateway'
import type { ServerTime } from '../gateway/types'
import type { ApiError } from '../shared/api/problem'
import { keys } from './queryKeys'
import { NO_RETRY, type Query } from './result'

const THIRTY_MINUTES = 30 * 60_000

/**
 * 서버 시각으로 앱 시계를 맞춘다(`clock.syncWith(gateway.time.get)`). 키 keys.serverTime.
 * 30분마다, 30분이 지난 뒤 창에 포커스가 돌아올 때 다시 맞춘다. 재동기가 실패해도 직전 data(와 시계)를 유지한다.
 */
export function useServerTimeSync(enabled: boolean): Query<ServerTime> {
  return useQuery<ServerTime, ApiError>({
    queryKey: keys.serverTime,
    queryFn: () => clock.syncWith(() => gateway.time.get()),
    enabled,
    staleTime: THIRTY_MINUTES,
    refetchInterval: THIRTY_MINUTES,
    refetchOnWindowFocus: true,
    ...NO_RETRY,
  })
}
