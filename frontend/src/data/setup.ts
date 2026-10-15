import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { DirectorySettingsInput, Me, SetupState } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.setup.status. 키 keys.setup. */
export function useSetupStatus(): Query<SetupState> {
  return useQuery<SetupState, ApiError>({ queryKey: keys.setup, queryFn: () => gateway.setup.status(), ...NO_RETRY })
}

/** gateway.setup.saveDirectory. 성공: keys.setup 무효화. */
export function useSaveSetupDirectory(): Mutation<DirectorySettingsInput> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, DirectorySettingsInput>({
    mutationFn: (input) => gateway.setup.saveDirectory(input),
    onSuccess: () => invalidate(keys.setup),
  })
}

/** gateway.setup.saveStorage(path). 성공: keys.setup 무효화. */
export function useSaveSetupStorage(): Mutation<string> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, string>({
    mutationFn: (path) => gateway.setup.saveStorage(path),
    onSuccess: () => invalidate(keys.setup),
  })
}

/** gateway.setup.testStorage(path). 최초 설정(로그인 전) 쓰기 테스트. 캐시 영향 없음. */
export function useTestSetupStorage(): Mutation<string> {
  return useMutation<void, ApiError, string>({ mutationFn: (path) => gateway.setup.testStorage(path) })
}

/** gateway.setup.registerAdmin. gcTime 0(비밀번호). 성공: keys.me, keys.setup 갱신(로그인된 상태). */
export function useRegisterAdmin(): Mutation<{ loginId: string; password: string }, Me> {
  const queryClient = useQueryClient()
  return useMutation<Me, ApiError, { loginId: string; password: string }>({
    mutationFn: ({ loginId, password }) => gateway.setup.registerAdmin(loginId, password),
    gcTime: 0,
    onSuccess: async (me) => {
      queryClient.setQueryData(keys.me, me)
      await queryClient.invalidateQueries({ queryKey: keys.setup })
    },
  })
}
