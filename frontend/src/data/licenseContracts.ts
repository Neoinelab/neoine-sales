import { keepPreviousData, useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ContractUploadResult } from '../gateway/types'
import type { ApiError } from '../shared/api/problem'
import type {
  ContractAttachment,
  DownloadedFile,
  LicenseContract,
  LicenseContractFields,
  LicenseContractQuery,
  LicenseIssueInput,
  Page,
  UploadInput,
} from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

export const CONTRACT_PAGE_SIZE = 50

/** 서버 `total`을 기준으로 다음 페이지가 있는지 본다. */
function nextOffset(last: Page<LicenseContract>): number | undefined {
  const next = last.offset + last.items.length
  return last.items.length > 0 && next < last.total ? next : undefined
}

/**
 * gateway.licenseContracts.list(query, offset, 50)를 무한 스크롤로 읽는다. 키 keys.licenseContractList.
 * 다른 사용자의 변경으로 쪽 경계가 밀려 겹친 행은 id로 한 번만 보인다.
 */
export function useLicenseContracts(query: LicenseContractQuery) {
  const result = useInfiniteQuery<Page<LicenseContract>, ApiError>({
    queryKey: keys.licenseContractList(query),
    queryFn: ({ pageParam }) => gateway.licenseContracts.list(query, pageParam as number, CONTRACT_PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: nextOffset,
    // 조건·정렬을 바꾸는 동안 이전 목록을 그대로 보여 준다(표가 깜박이지 않게).
    placeholderData: keepPreviousData,
    ...NO_RETRY,
  })
  const pages = result.data?.pages ?? []
  const seen = new Set<number>()
  const items: LicenseContract[] = []
  for (const page of pages) {
    for (const item of page.items) {
      if (seen.has(item.id)) continue
      seen.add(item.id)
      items.push(item)
    }
  }
  return { ...result, items, total: pages.at(-1)?.total ?? 0, pageCount: pages.length }
}

/** 변경 뒤 목록은 처음(첫 쪽)부터 다시 읽는다: 불러 둔 쪽을 모두 다시 받지 않도록 목록 쿼리를 초기화한다. */
function useRefreshContracts(): () => Promise<void> {
  const queryClient = useQueryClient()
  return async () => {
    await queryClient.resetQueries({ queryKey: keys.licenseContractLists })
  }
}

/** 계약 변경은 Deal 쪽 값(`licenseContractCount`, 삭제 영향)에도 닿으므로 Deal 쿼리도 갱신한다. */
function useRefreshAfterChange(): () => Promise<void> {
  const refresh = useRefreshContracts()
  const invalidate = useInvalidate()
  return async () => {
    await Promise.all([refresh(), invalidate(keys.deals)])
  }
}

export function useUpdateContract(): Mutation<{ id: number; fields: LicenseContractFields }, LicenseContract> {
  const refresh = useRefreshAfterChange()
  return useMutation<LicenseContract, ApiError, { id: number; fields: LicenseContractFields }>({
    mutationFn: ({ id, fields }) => gateway.licenseContracts.update(id, fields),
    onSuccess: () => refresh(),
  })
}

export function useIssueContract(): Mutation<{ id: number; input: LicenseIssueInput }, LicenseContract> {
  const refresh = useRefreshAfterChange()
  return useMutation<LicenseContract, ApiError, { id: number; input: LicenseIssueInput }>({
    mutationFn: ({ id, input }) => gateway.licenseContracts.issue(id, input),
    onSuccess: () => refresh(),
  })
}

/** 갱신은 새 계약을 돌려주고 이전 계약은 종료된다. */
export function useRenewContract(): Mutation<{ id: number; input: LicenseIssueInput }, LicenseContract> {
  const refresh = useRefreshAfterChange()
  return useMutation<LicenseContract, ApiError, { id: number; input: LicenseIssueInput }>({
    mutationFn: ({ id, input }) => gateway.licenseContracts.renew(id, input),
    onSuccess: () => refresh(),
  })
}

export function useEndContract(): Mutation<number, LicenseContract> {
  const refresh = useRefreshAfterChange()
  return useMutation<LicenseContract, ApiError, number>({
    mutationFn: (id) => gateway.licenseContracts.end(id),
    onSuccess: () => refresh(),
  })
}

export function useRemoveContract(): Mutation<number> {
  const refresh = useRefreshAfterChange()
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => gateway.licenseContracts.remove(id),
    onSuccess: () => refresh(),
  })
}

/** gateway.licenseContracts.attachments.list(contractId). contractId가 undefined면 비활성. */
export function useContractAttachments(contractId: number | undefined): Query<ContractAttachment[]> {
  return useQuery<ContractAttachment[], ApiError>({
    queryKey: keys.licenseContractAttachments(contractId ?? 0),
    queryFn: () => gateway.licenseContracts.attachments.list(contractId ?? 0),
    enabled: contractId !== undefined,
    ...NO_RETRY,
  })
}

/**
 * 업로드. onExists='ask'에서 같은 이름이면 ApiError(409, kind 'file-exists') — 화면이 교체/건너뛰기를 물은 뒤 'replace'/'skip'으로 다시 호출한다.
 * 성공: 그 계약의 첨부 목록과 계약 목록(첨부 건수)을 다시 읽는다.
 */
export function useUploadContractAttachment(): Mutation<{ contractId: number; input: UploadInput }, ContractUploadResult> {
  const invalidate = useInvalidate()
  return useMutation<ContractUploadResult, ApiError, { contractId: number; input: UploadInput }>({
    mutationFn: ({ contractId, input }) => gateway.licenseContracts.attachments.upload(contractId, input),
    onSuccess: (_result, { contractId }) => invalidate(keys.licenseContractAttachments(contractId), keys.licenseContractLists),
  })
}

export function useRemoveContractAttachment(): Mutation<{ contractId: number; attachmentId: number }> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, { contractId: number; attachmentId: number }>({
    mutationFn: ({ attachmentId }) => gateway.licenseContracts.attachments.remove(attachmentId),
    onSuccess: (_result, { contractId }) => invalidate(keys.licenseContractAttachments(contractId), keys.licenseContractLists),
  })
}

export function useDownloadContractAttachment(): Mutation<number, DownloadedFile> {
  return useMutation<DownloadedFile, ApiError, number>({ mutationFn: (id) => gateway.licenseContracts.attachments.download(id) })
}
