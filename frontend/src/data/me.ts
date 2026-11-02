import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { MyProfile, ProfileChange } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.me.profile. 키 keys.myProfile. 로그인한 모든 역할. */
export function useMyProfile(): Query<MyProfile> {
  return useQuery<MyProfile, ApiError>({ queryKey: keys.myProfile, queryFn: () => gateway.me.profile(), ...NO_RETRY })
}

/** gateway.me.updateProfile. 성공: 응답으로 keys.myProfile을 채우고, 상단 바 이름(keys.me)과 이름이 보이는 목록을 갱신한다. */
export function useUpdateMyProfile(): Mutation<ProfileChange, MyProfile> {
  const queryClient = useQueryClient()
  const invalidate = useInvalidate()
  return useMutation<MyProfile, ApiError, ProfileChange>({
    mutationFn: (change) => gateway.me.updateProfile(change),
    onSuccess: async (profile) => {
      queryClient.setQueryData(keys.myProfile, profile)
      await invalidate(keys.me, keys.users, keys.deals, keys.forecast)
    },
  })
}

/** gateway.me.changePassword(current, next). gcTime 0(비밀번호가 든 variables를 캐시에 남기지 않는다). 캐시는 바뀌지 않는다. */
export function useChangeMyPassword(): Mutation<{ current: string; next: string }> {
  return useMutation<void, ApiError, { current: string; next: string }>({
    mutationFn: ({ current, next }) => gateway.me.changePassword(current, next),
    gcTime: 0,
  })
}
