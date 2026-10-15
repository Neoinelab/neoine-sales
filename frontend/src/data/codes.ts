import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { CodeCreateInput, CodeKind, CodeSet, CodeWithUsage } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.codes.all. 키 keys.codeSet. 배지·select·sync 규칙의 입력(모든 역할). 변경 훅이 무효화한다. */
export function useCodeSet(): Query<CodeSet> {
  return useQuery<CodeSet, ApiError>({
    queryKey: keys.codeSet,
    queryFn: () => gateway.codes.all(),
    staleTime: Infinity,
    ...NO_RETRY,
  })
}

/** gateway.codes.list(kind). 키 keys.codeList(kind). 관리 화면(사용 중 건수 포함). */
export function useCodes(kind: CodeKind): Query<CodeWithUsage[]> {
  return useQuery<CodeWithUsage[], ApiError>({ queryKey: keys.codeList(kind), queryFn: () => gateway.codes.list(kind), ...NO_RETRY })
}

/** gateway.codes.create. 성공: keys.codes 전체 무효화. */
export function useCreateCode(): Mutation<CodeCreateInput, CodeWithUsage> {
  const invalidate = useInvalidate()
  return useMutation<CodeWithUsage, ApiError, CodeCreateInput>({
    mutationFn: (input) => gateway.codes.create(input),
    onSuccess: () => invalidate(keys.codes),
  })
}

/** gateway.codes.rename. 성공: keys.codes + keys.deals + keys.forecast 무효화(이름이 목록·상세에 즉시 반영). */
export function useRenameCode(): Mutation<{ id: string; name: string }, CodeWithUsage> {
  const invalidate = useInvalidate()
  return useMutation<CodeWithUsage, ApiError, { id: string; name: string }>({
    mutationFn: ({ id, name }) => gateway.codes.rename(id, name),
    onSuccess: () => invalidate(keys.codes, keys.deals, keys.forecast),
  })
}

/** gateway.codes.reorder. 성공: keys.codes + keys.deals + keys.forecast 무효화. */
export function useReorderCodes(): Mutation<{ kind: CodeKind; orderedIds: string[] }, CodeWithUsage[]> {
  const invalidate = useInvalidate()
  return useMutation<CodeWithUsage[], ApiError, { kind: CodeKind; orderedIds: string[] }>({
    mutationFn: ({ kind, orderedIds }) => gateway.codes.reorder(kind, orderedIds),
    onSuccess: () => invalidate(keys.codes, keys.deals, keys.forecast),
  })
}

/** gateway.codes.remove(id). 성공: keys.codes 무효화. 거부는 409(ApiError). */
export function useRemoveCode(): Mutation<string> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, string>({
    mutationFn: (id) => gateway.codes.remove(id),
    onSuccess: () => invalidate(keys.codes),
  })
}
