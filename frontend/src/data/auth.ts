import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import { canAccessAdmin, canWrite } from '../shared/model/permissions'
import type { Me } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, type Mutation, type Query } from './result'

/** gateway.auth.me. 키 keys.me. retry 없음(401은 곧 비로그인). staleTime 60s. */
export function useMe(): Query<Me> {
  return useQuery<Me, ApiError>({ queryKey: keys.me, queryFn: () => gateway.auth.me(), staleTime: 60_000, ...NO_RETRY })
}

/**
 * gateway.auth.login. gcTime 0(비밀번호가 든 variables를 캐시에 남기지 않는다).
 * 성공: keys.me 갱신. 이동(`/`)은 호출 화면이 한다.
 */
export function useLogin(): Mutation<{ loginId: string; password: string }, Me> {
  const queryClient = useQueryClient()
  return useMutation<Me, ApiError, { loginId: string; password: string }>({
    mutationFn: ({ loginId, password }) => gateway.auth.login(loginId, password),
    gcTime: 0,
    onSuccess: (me) => queryClient.setQueryData(keys.me, me),
  })
}

/** gateway.auth.quickLogin(userId). 성공 처리는 useLogin과 같다. */
export function useQuickLogin(): Mutation<string, Me> {
  const queryClient = useQueryClient()
  return useMutation<Me, ApiError, string>({
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
