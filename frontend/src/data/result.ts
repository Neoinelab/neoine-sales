import { useQueryClient, type UseMutationResult, type UseQueryResult } from '@tanstack/react-query'
import type { ApiError } from '../shared/api/problem'

/** 모든 조회 훅의 반환 타입. 오류는 항상 ApiError(게이트웨이 규약). */
export type Query<T> = UseQueryResult<T, ApiError>

/** 모든 변경 훅의 반환 타입. `mutateAsync`가 ApiError로 reject한다. */
export type Mutation<TVariables, TData = void> = UseMutationResult<TData, ApiError, TVariables>

/** 서버 오류(권한·검증 등)는 재시도해도 같으므로 조회는 재시도하지 않는다. */
export const NO_RETRY = { retry: false } as const

/**
 * 변경 성공 후 쿼리를 무효화하는 함수를 돌려준다. 돌려준 Promise는 활성 쿼리의 재조회가 끝나면 resolve되므로
 * `onSuccess`에서 그대로 반환하면 `mutateAsync`가 화면 데이터가 갱신된 뒤에 끝난다.
 */
export function useInvalidate(): (...queryKeys: readonly (readonly unknown[])[]) => Promise<void> {
  const queryClient = useQueryClient()
  return async (...queryKeys) => {
    await Promise.all(queryKeys.map((queryKey) => queryClient.invalidateQueries({ queryKey })))
  }
}
