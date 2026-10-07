import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'

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
