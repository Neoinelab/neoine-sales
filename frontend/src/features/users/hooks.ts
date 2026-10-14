import { type QueryClient, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'

export type AppUser = Schemas['UserResponse']
export type UserStatusFilter = 'active' | 'resigned' | 'all'

export function useUsers(status: UserStatusFilter) {
  return useQuery({
    queryKey: ['users', status],
    queryFn: () => call(api.GET('/api/v1/users', { params: { query: { offset: 0, limit: 50, status } } })),
  })
}

/** 사용자 목록과 선택 후보(user-options, staleTime 30초)를 함께 갱신해 퇴사자가 후보에 남지 않게 한다. */
function refreshUsers(client: QueryClient) {
  return Promise.all([
    client.invalidateQueries({ queryKey: ['users'] }),
    client.invalidateQueries({ queryKey: ['user-options'] }),
  ])
}

export function useAddUser() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['UserRequest']) => call(api.POST('/api/v1/users', { body })),
    onSuccess: () => refreshUsers(client),
  })
}

/** 삭제 사유는 현재 '퇴사' 하나뿐이라 reason을 보내지 않는다(서버 기본값). 응답의 outcome으로 결과를 구분한다. */
export function useDeleteUser() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => call(api.DELETE('/api/v1/users/{user_id}', { params: { path: { user_id: id } } })),
    onSuccess: () => refreshUsers(client),
  })
}
