import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ApplyChangeResult } from '../gateway/types'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type {
  ApplyChangeRequest,
  DealDeletionImpact,
  DealDetail,
  DealInput,
  DealListQuery,
  DealPatch,
  DealRow,
  Page,
  UpdatedPeriods,
} from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/**
 * gateway.deals.list(query). 키 keys.dealList(query). 화면은 URL 쿼리를 DealListQuery로 만들어 넘긴다.
 * 조건·페이지가 바뀌는 동안 이전 결과를 유지한다(`keepPreviousData`): 표가 로딩 문구로 바뀌며 깜빡이지 않는다.
 */
export function useDeals(query: DealListQuery): Query<Page<DealRow>> {
  return useQuery<Page<DealRow>, ApiError>({
    queryKey: keys.dealList(query),
    queryFn: () => gateway.deals.list(query),
    placeholderData: keepPreviousData,
    ...NO_RETRY,
  })
}

/** gateway.deals.updatedPeriods(). 키 keys.updatedPeriods. 최종 업데이트 프리셋의 날짜는 서버가 푼 값을 그대로 쓴다. */
export function useUpdatedPeriods(): Query<UpdatedPeriods> {
  return useQuery<UpdatedPeriods, ApiError>({
    queryKey: keys.updatedPeriods,
    queryFn: () => gateway.deals.updatedPeriods(),
    ...NO_RETRY,
  })
}

/** gateway.deals.get(code). 키 keys.deal(code). code가 undefined면 비활성. 없으면 ApiError 404. */
export function useDeal(code: string | undefined): Query<DealDetail> {
  return useQuery<DealDetail, ApiError>({
    queryKey: keys.deal(code ?? ''),
    queryFn: () => gateway.deals.get(code ?? ''),
    enabled: code !== undefined,
    ...NO_RETRY,
  })
}

/** gateway.deals.impact(code). 키 keys.dealImpact(code). 삭제 팝업이 열릴 때만 enabled를 true로 준다. */
export function useDealImpact(code: string | undefined, enabled: boolean): Query<DealDeletionImpact> {
  return useQuery<DealDeletionImpact, ApiError>({
    queryKey: keys.dealImpact(code ?? ''),
    queryFn: () => gateway.deals.impact(code ?? ''),
    enabled: enabled && code !== undefined,
    ...NO_RETRY,
  })
}

/** gateway.deals.create. 성공: keys.deals + keys.contacts + keys.forecast 무효화. 반환 DealDetail.code로 상세로 이동한다. */
export function useCreateDeal(): Mutation<DealInput, DealDetail> {
  const invalidate = useInvalidate()
  return useMutation<DealDetail, ApiError, DealInput>({
    mutationFn: (input) => gateway.deals.create(input),
    onSuccess: () => invalidate(keys.deals, keys.contacts, keys.labels, keys.forecast, keys.historyAll),
  })
}

/** gateway.deals.update(code, patch). 성공: keys.deals + keys.contacts + keys.labels + keys.history(code) + keys.forecast 무효화. */
export function useUpdateDeal(): Mutation<{ code: string; patch: DealPatch }, DealDetail> {
  const invalidate = useInvalidate()
  return useMutation<DealDetail, ApiError, { code: string; patch: DealPatch }>({
    mutationFn: ({ code, patch }) => gateway.deals.update(code, patch),
    onSuccess: (_deal, { code }) => invalidate(keys.deals, keys.contacts, keys.labels, keys.history(code), keys.forecast),
  })
}

/**
 * gateway.deals.applyChange(code, request). 목록 Inline Update·상세 현재값 바.
 * 성공: keys.deals + keys.history(code) + keys.forecast 무효화. 호출 전 `useSyncedChange`(A-3)로 request.resolution을 만든다.
 */
export function useApplyDealChange(): Mutation<{ code: string; request: ApplyChangeRequest }, ApplyChangeResult> {
  const invalidate = useInvalidate()
  return useMutation<ApplyChangeResult, ApiError, { code: string; request: ApplyChangeRequest }>({
    mutationFn: ({ code, request }) => gateway.deals.applyChange(code, request),
    onSuccess: (_result, { code }) => invalidate(keys.deals, keys.history(code), keys.forecast),
  })
}

/**
 * gateway.deals.remove(code, confirmCode). 성공: 해당 code의 상세·impact·actions·history·attachments 쿼리를 제거하고
 * keys.deals + keys.forecast를 무효화한다.
 */
export function useRemoveDeal(): Mutation<{ code: string; confirmCode: string }> {
  const queryClient = useQueryClient()
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, { code: string; confirmCode: string }>({
    mutationFn: ({ code, confirmCode }) => gateway.deals.remove(code, confirmCode),
    onSuccess: (_result, { code }) => {
      for (const queryKey of [keys.deal(code), keys.dealImpact(code), keys.actions(code), keys.history(code), keys.attachments(code)]) {
        queryClient.removeQueries({ queryKey })
      }
      return invalidate(keys.deals, keys.forecast)
    },
  })
}
