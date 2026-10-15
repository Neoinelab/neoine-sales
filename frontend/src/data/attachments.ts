import { useMutation, useQuery } from '@tanstack/react-query'
import type { UploadResult } from '../gateway/types'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { Attachment, DownloadedFile, UploadInput } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.attachments.list(dealCode). 키 keys.attachments(dealCode). dealCode가 undefined면 비활성. */
export function useAttachments(dealCode: string | undefined): Query<Attachment[]> {
  return useQuery<Attachment[], ApiError>({
    queryKey: keys.attachments(dealCode ?? ''),
    queryFn: () => gateway.attachments.list(dealCode ?? ''),
    enabled: dealCode !== undefined,
    ...NO_RETRY,
  })
}

/**
 * gateway.attachments.upload. onExists='ask'에서 같은 이름이면 ApiError(409, kind 'file-exists') —
 * 화면이 교체/건너뛰기를 물은 뒤 같은 mutation을 'replace'/'skip'으로 다시 호출한다.
 * 성공: keys.attachments(dealCode) + keys.history(dealCode) + keys.deals(상세·목록의 최종 업데이트) 무효화.
 */
export function useUploadAttachment(): Mutation<{ dealCode: string; input: UploadInput }, UploadResult> {
  const invalidate = useInvalidate()
  return useMutation<UploadResult, ApiError, { dealCode: string; input: UploadInput }>({
    mutationFn: ({ dealCode, input }) => gateway.attachments.upload(dealCode, input),
    onSuccess: (_result, { dealCode }) => invalidate(keys.attachments(dealCode), keys.history(dealCode), keys.deals),
  })
}

/** gateway.attachments.remove(id). 성공 무효화는 upload와 같다(dealCode는 호출 변수로 받는다). */
export function useRemoveAttachment(): Mutation<{ dealCode: string; attachmentId: string }> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, { dealCode: string; attachmentId: string }>({
    mutationFn: ({ attachmentId }) => gateway.attachments.remove(attachmentId),
    onSuccess: (_result, { dealCode }) => invalidate(keys.attachments(dealCode), keys.history(dealCode), keys.deals),
  })
}

/** gateway.attachments.download(id). 캐시 영향 없음. 호출 화면이 blob을 objectURL로 내려받는다. */
export function useDownloadAttachment(): Mutation<string, DownloadedFile> {
  return useMutation<DownloadedFile, ApiError, string>({ mutationFn: (id) => gateway.attachments.download(id) })
}
