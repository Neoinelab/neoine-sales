import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type {
  User,
  UserCreateInput,
  UserListFilter,
  UserOptionsQuery,
  UserRef,
  UserRemoveResult,
} from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.users.list(filter). 키 keys.userList. admin 화면 전용. */
export function useUsers(filter: UserListFilter): Query<User[]> {
  return useQuery<User[], ApiError>({ queryKey: keys.userList(filter), queryFn: () => gateway.users.list(filter), ...NO_RETRY })
}

/** gateway.users.options(query). 키 keys.userOptions. UserSelect·필터·Owner 후보. */
export function useUserOptions(query: UserOptionsQuery = {}): Query<UserRef[]> {
  return useQuery<UserRef[], ApiError>({
    queryKey: keys.userOptions(query),
    queryFn: () => gateway.users.options(query),
    ...NO_RETRY,
  })
}

/** gateway.users.create. 성공: keys.users 무효화. */
export function useCreateUser(): Mutation<UserCreateInput, User> {
  const invalidate = useInvalidate()
  return useMutation<User, ApiError, UserCreateInput>({
    mutationFn: (input) => gateway.users.create(input),
    onSuccess: () => invalidate(keys.users),
  })
}

/** gateway.users.remove(id). 성공: keys.users 무효화(퇴사 처리된 사용자는 표기가 바뀌므로 keys.deals·keys.forecast도). */
export function useRemoveUser(): Mutation<number, UserRemoveResult> {
  const invalidate = useInvalidate()
  return useMutation<UserRemoveResult, ApiError, number>({
    mutationFn: (id) => gateway.users.remove(id),
    onSuccess: () => invalidate(keys.users, keys.deals, keys.forecast),
  })
}
