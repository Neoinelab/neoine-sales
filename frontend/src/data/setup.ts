import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { AuthMode, DirectorySettingsInput, Me, NewAccountProfile, SetupState } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.setup.status. 키 keys.setup. */
export function useSetupStatus(): Query<SetupState> {
  return useQuery<SetupState, ApiError>({ queryKey: keys.setup, queryFn: () => gateway.setup.status(), ...NO_RETRY })
}

/** gateway.setup.chooseAuthMode. 성공: keys.setup·keys.authConfig 갱신(끝나면 단계가 바뀐 상태). */
export function useChooseAuthMode(): Mutation<AuthMode> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, AuthMode>({
    mutationFn: (mode) => gateway.setup.chooseAuthMode(mode),
    onSuccess: () => invalidate(keys.setup, keys.authConfig),
  })
}

/** gateway.setup.saveDirectory. 성공: keys.setup 무효화. */
export function useSaveSetupDirectory(): Mutation<DirectorySettingsInput> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, DirectorySettingsInput>({
    mutationFn: (input) => gateway.setup.saveDirectory(input),
    onSuccess: () => invalidate(keys.setup, keys.authConfig),
  })
}

/** gateway.setup.testDirectory. 최초 설정(로그인 전) AD 연결 테스트. 캐시 영향 없음. */
export function useTestSetupDirectory(): Mutation<DirectorySettingsInput, { baseDn: string }> {
  return useMutation<{ baseDn: string }, ApiError, DirectorySettingsInput>({ mutationFn: (input) => gateway.setup.testDirectory(input) })
}

/** gateway.setup.saveStorage(path). 성공: keys.setup 무효화. */
export function useSaveSetupStorage(): Mutation<string> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, string>({
    mutationFn: (path) => gateway.setup.saveStorage(path),
    onSuccess: () => invalidate(keys.setup, keys.authConfig),
  })
}

/** gateway.setup.testStorage(path). 최초 설정(로그인 전) 쓰기 테스트. 캐시 영향 없음. */
export function useTestSetupStorage(): Mutation<string> {
  return useMutation<void, ApiError, string>({ mutationFn: (path) => gateway.setup.testStorage(path) })
}

export interface RegisterAdminVariables {
  loginId: string
  password: string
  /** local 모드에서만(AD 모드는 생략). */
  profile?: NewAccountProfile
}

/** gateway.setup.registerAdmin. gcTime 0(비밀번호). 성공: keys.me, keys.setup 갱신(로그인된 상태). */
export function useRegisterAdmin(): Mutation<RegisterAdminVariables, Me> {
  const queryClient = useQueryClient()
  return useMutation<Me, ApiError, RegisterAdminVariables>({
    mutationFn: ({ loginId, password, profile }) => gateway.setup.registerAdmin(loginId, password, profile),
    gcTime: 0,
    onSuccess: async (me) => {
      queryClient.setQueryData(keys.me, me)
      await queryClient.invalidateQueries({ queryKey: keys.setup })
    },
  })
}
