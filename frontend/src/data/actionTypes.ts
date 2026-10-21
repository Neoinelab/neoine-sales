import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { ActionTypeWithUsage } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.actionTypes.list. 키 keys.actionTypes. */
export function useActionTypes(): Query<ActionTypeWithUsage[]> {
  return useQuery<ActionTypeWithUsage[], ApiError>({
    queryKey: keys.actionTypes,
    queryFn: () => gateway.actionTypes.list(),
    ...NO_RETRY,
  })
}

/** gateway.actionTypes.create(name). 성공: keys.actionTypes 무효화. */
export function useCreateActionType(): Mutation<string, ActionTypeWithUsage> {
  const invalidate = useInvalidate()
  return useMutation<ActionTypeWithUsage, ApiError, string>({
    mutationFn: (name) => gateway.actionTypes.create(name),
    onSuccess: () => invalidate(keys.actionTypes),
  })
}

/** gateway.actionTypes.rename. 성공: keys.actionTypes + Action 목록(표의 유형 이름) 무효화. */
export function useRenameActionType(): Mutation<{ id: number; name: string }, ActionTypeWithUsage> {
  const invalidate = useInvalidate()
  return useMutation<ActionTypeWithUsage, ApiError, { id: number; name: string }>({
    mutationFn: ({ id, name }) => gateway.actionTypes.rename(id, name),
    onSuccess: () => invalidate(keys.actionTypes, ['actions']),
  })
}

/** gateway.actionTypes.remove(id). 성공: keys.actionTypes 무효화. */
export function useRemoveActionType(): Mutation<number> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => gateway.actionTypes.remove(id),
    onSuccess: () => invalidate(keys.actionTypes),
  })
}
