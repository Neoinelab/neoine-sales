import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { api, type Schemas } from '../../shared/api/client'
import { ApiError, call } from '../../shared/api/problem'

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => call(api.GET('/api/v1/auth/me')),
    retry: false,
    staleTime: 60_000,
  })
}

export function useAuthConfig() {
  return useQuery({
    queryKey: ['auth-config'],
    queryFn: () => call(api.GET('/api/v1/auth/config')),
    staleTime: Infinity,
  })
}

export function useDevLogin() {
  const client = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: (role: Schemas['Role']) =>
      call(api.POST('/api/v1/auth/dev-login', { body: { role } })),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['me'] })
      void navigate('/')
    },
  })
}

export function useLogout() {
  const client = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    mutationFn: () => call(api.POST('/api/v1/auth/logout')),
    onSuccess: () => {
      client.clear()
      void navigate('/login')
    },
  })
}

/** 로그인한 사용자의 역할에서 화면 권한을 정한다. 사용자를 모르는 동안(로딩·401)은 모두 false. */
export function usePermissions(): { canWrite: boolean; isAdmin: boolean } {
  const role = useMe().data?.role
  return { canWrite: role === 'admin' || role === 'sales', isAdmin: role === 'admin' }
}

// 비밀번호가 든 variables를 화면이 사라진 뒤 캐시(기본 5분)에 남기지 않는다.
export function useLogin() {
  const client = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    gcTime: 0,
    mutationFn: (body: Schemas['LoginRequest']) => call(api.POST('/api/v1/auth/login', { body })),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['me'] })
      void navigate('/')
    },
  })
}

/** 최초 관리자 등록(AD 계정). 성공하면 이미 로그인된 상태다. */
export function useSetupAdmin() {
  const client = useQueryClient()
  const navigate = useNavigate()
  return useMutation({
    gcTime: 0,
    mutationFn: (body: Schemas['SetupAdminRequest']) => call(api.POST('/api/v1/auth/setup', { body })),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ['me'] })
      void navigate('/')
      // 화면을 떠난 뒤에 갱신해야 마법사가 "설정 끝" 상태를 보고 로그인 화면으로 튀지 않는다.
      void client.invalidateQueries({ queryKey: ['auth-config'] })
    },
    onError: (error) => {
      // 그 사이 다른 사람이 관리자를 등록했으면(409) config를 다시 읽어 로그인 화면으로 보낸다.
      if (error instanceof ApiError && error.status === 409) {
        void client.invalidateQueries({ queryKey: ['auth-config'] })
      }
    },
  })
}
