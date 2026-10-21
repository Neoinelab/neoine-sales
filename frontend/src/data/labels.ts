import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { BantCategory, BantLabelWithUsage } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.labels.list. 키 keys.labels. */
export function useLabels(): Query<BantLabelWithUsage[]> {
  return useQuery<BantLabelWithUsage[], ApiError>({ queryKey: keys.labels, queryFn: () => gateway.labels.list(), ...NO_RETRY })
}

/** gateway.labels.create(category, name). 성공: keys.labels 무효화. 반환된 Label은 호출 화면이 즉시 선택한다. */
export function useCreateLabel(): Mutation<{ category: BantCategory; name: string }, BantLabelWithUsage> {
  const invalidate = useInvalidate()
  return useMutation<BantLabelWithUsage, ApiError, { category: BantCategory; name: string }>({
    mutationFn: ({ category, name }) => gateway.labels.create(category, name),
    onSuccess: () => invalidate(keys.labels),
  })
}

/** gateway.labels.rename. 성공: keys.labels + keys.deals 무효화. */
export function useRenameLabel(): Mutation<{ id: number; name: string }, BantLabelWithUsage> {
  const invalidate = useInvalidate()
  return useMutation<BantLabelWithUsage, ApiError, { id: number; name: string }>({
    mutationFn: ({ id, name }) => gateway.labels.rename(id, name),
    onSuccess: () => invalidate(keys.labels, keys.deals),
  })
}

/** gateway.labels.remove(id). 성공: keys.labels 무효화. */
export function useRemoveLabel(): Mutation<number> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => gateway.labels.remove(id),
    onSuccess: () => invalidate(keys.labels),
  })
}
