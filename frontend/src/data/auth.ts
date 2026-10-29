import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { AuthConfig } from '../gateway/types'
import type { ApiError } from '../shared/api/problem'
import { canAccessAdmin, canWrite } from '../shared/model/permissions'
import type { DirectoryWarning, LoginResult, Me } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, type Mutation, type Query } from './result'

/** gateway.auth.me. 키 keys.me. retry 없음(401은 곧 비로그인). staleTime 60s. */
export function useMe(): Query<Me> {
  return useQuery<Me, ApiError>({ queryKey: keys.me, queryFn: () => gateway.auth.me(), staleTime: 60_000, ...NO_RETRY })
}

/** gateway.auth.config. 키 keys.authConfig. 로그인 화면이 빠른 로그인을 그릴지 정한다(로그인 전에도 읽는다). */
export function useAuthConfig(): Query<AuthConfig> {
  return useQuery<AuthConfig, ApiError>({ queryKey: keys.authConfig, queryFn: () => gateway.auth.config(), ...NO_RETRY })
}

/**
 * gateway.auth.login. gcTime 0(비밀번호가 든 variables를 캐시에 남기지 않는다).
 * 성공: keys.me 갱신, AD 경고(있으면)는 keys.directoryWarning에 메모리로만 둔다. 이동(`/`)은 호출 화면이 한다.
 */
export function useLogin(): Mutation<{ loginId: string; password: string }, LoginResult> {
  const queryClient = useQueryClient()
  return useMutation<LoginResult, ApiError, { loginId: string; password: string }>({
    mutationFn: ({ loginId, password }) => gateway.auth.login(loginId, password),
    gcTime: 0,
    onSuccess: ({ me, directoryWarning }) => {
      queryClient.setQueryData(keys.me, me)
      queryClient.setQueryData(keys.directoryWarning, directoryWarning)
    },
  })
}

/** 로그인 응답으로 받은 AD 경고(없거나 닫았으면 null). 서버에 다시 묻지 않는다. */
export function useDirectoryWarning(): { warning: DirectoryWarning | null; dismiss: () => void } {
  const queryClient = useQueryClient()
  const { data } = useQuery<DirectoryWarning | null>({
    queryKey: keys.directoryWarning,
    queryFn: () => null,
    enabled: false,
    staleTime: Infinity,
    gcTime: Infinity,
  })
  return { warning: data ?? null, dismiss: () => queryClient.setQueryData(keys.directoryWarning, null) }
}

/** gateway.auth.quickLogin(userId). 성공 처리는 useLogin과 같다. */
export function useQuickLogin(): Mutation<number, Me> {
  const queryClient = useQueryClient()
  return useMutation<Me, ApiError, number>({
    mutationFn: (userId) => gateway.auth.quickLogin(userId),
    gcTime: 0,
    onSuccess: (me) => queryClient.setQueryData(keys.me, me),
  })
}

/** gateway.auth.logout. 성공: 쿼리 캐시 전체 clear. 이동(`/login`)은 호출 화면이 한다. */
export function useLogout(): Mutation<void> {
  const queryClient = useQueryClient()
  return useMutation<void, ApiError, void>({
    mutationFn: () => gateway.auth.logout(),
    onSuccess: () => queryClient.clear(),
  })
}

export interface Permissions {
  /** 사용자를 알기 전(로딩·401)에는 role이 null이고 나머지는 모두 false. */
  role: Me['role'] | null
  me: Me | null
  canWrite: boolean
  isAdmin: boolean
}

/** 기존 `usePermissions()`의 호환 시그니처({canWrite,isAdmin}) + role/me. useMe 결과로 permissions.ts 함수를 적용한다. */
export function permissionsFor(me: Me | null | undefined): Permissions {
  const role = me?.role ?? null
  return { role, me: me ?? null, canWrite: canWrite(role), isAdmin: canAccessAdmin(role) }
}

export function usePermissions(): Permissions {
  const { data } = useMe()
  return permissionsFor(data)
}
