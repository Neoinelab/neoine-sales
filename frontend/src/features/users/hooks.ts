import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'

export type AppUser = Schemas['UserResponse']

export function useUsers() {
  return useQuery({
    queryKey: ['users'],
    queryFn: () => call(api.GET('/api/v1/users', { params: { query: { offset: 0, limit: 50 } } })),
  })
}

export function useAddUser() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['UserRequest']) => call(api.POST('/api/v1/users', { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ['users'] }),
  })
}

export function useDeleteUser() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => call(api.DELETE('/api/v1/users/{user_id}', { params: { path: { user_id: id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: ['users'] }),
  })
}
