import { useIsMutating, useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { CommentCounts, DealComment } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** 한 번에 읽음 처리할 수 있는 id 수(서버 한도). */
export const MARK_READ_CHUNK = 500

/** gateway.comments.list(dealCode, {actionId}). 최근순. actionId를 주면 그 Action의 Comment만. dealCode가 undefined면 비활성. */
export function useComments(dealCode: string | undefined, actionId: number | null = null): Query<DealComment[]> {
  return useQuery<DealComment[], ApiError>({
    queryKey: keys.commentList(dealCode ?? '', actionId),
    queryFn: () => gateway.comments.list(dealCode ?? '', actionId === null ? {} : { actionId }),
    enabled: dealCode !== undefined,
    ...NO_RETRY,
  })
}

/** gateway.comments.counts(dealCode). Deal·Action별 읽지 않은 수. 실패해도 화면은 배지만 숨긴다. */
export function useCommentCounts(dealCode: string | undefined): Query<CommentCounts> {
  return useQuery<CommentCounts, ApiError>({
    queryKey: keys.commentCounts(dealCode ?? ''),
    queryFn: () => gateway.comments.counts(dealCode ?? ''),
    enabled: dealCode !== undefined,
    ...NO_RETRY,
  })
}

/** 작성·삭제·읽음 처리 성공 뒤 Comment 목록·집계와 Deal History를 다시 읽는다. */
function useInvalidateComments(): (dealCode: string) => Promise<void> {
  const invalidate = useInvalidate()
  return (dealCode) => invalidate(keys.comments(dealCode), keys.history(dealCode))
}

const WRITE_KEY = ['comment-write'] as const

/** Comment 작성·삭제가 진행 중인지. 상세 팝업이 이 동안 닫히지 않게 하고 입력 칸을 잠근다. */
export function useCommentWriting(): boolean {
  return useIsMutating({ mutationKey: WRITE_KEY }) > 0
}

/** gateway.comments.create(dealCode, {body, actionId?}). */
export function useCreateComment(): Mutation<{ dealCode: string; body: string; actionId?: number }, DealComment> {
  const invalidate = useInvalidateComments()
  return useMutation<DealComment, ApiError, { dealCode: string; body: string; actionId?: number }>({
    mutationKey: WRITE_KEY,
    mutationFn: ({ dealCode, body, actionId }) => gateway.comments.create(dealCode, { body, ...(actionId === undefined ? {} : { actionId }) }),
    onSuccess: (_comment, { dealCode }) => invalidate(dealCode),
  })
}

/** gateway.comments.remove(commentId). */
export function useRemoveComment(): Mutation<{ dealCode: string; commentId: number }> {
  const invalidate = useInvalidateComments()
  return useMutation<void, ApiError, { dealCode: string; commentId: number }>({
    mutationKey: WRITE_KEY,
    mutationFn: ({ commentId }) => gateway.comments.remove(commentId),
    onSuccess: (_result, { dealCode }) => invalidate(dealCode),
  })
}

/** gateway.comments.markRead(dealCode, ids). Owner만. id가 500개를 넘으면 나눠 보낸다. 읽음 처리는 History를 남기지 않으므로 Comment 키만 무효화한다. */
export function useMarkCommentsRead(): Mutation<{ dealCode: string; commentIds: readonly number[] }> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, { dealCode: string; commentIds: readonly number[] }>({
    mutationFn: async ({ dealCode, commentIds }) => {
      for (let at = 0; at < commentIds.length; at += MARK_READ_CHUNK) {
        await gateway.comments.markRead(dealCode, commentIds.slice(at, at + MARK_READ_CHUNK))
      }
    },
    onSettled: (_result, _error, { dealCode }) => invalidate(keys.comments(dealCode)),
  })
}
