import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'
import { PAGE_SIZE } from '../../shared/constants'
import type { DealStage } from './stages'

export type Deal = Schemas['DealResponse']
export type DealInput = Schemas['DealRequest']

export interface DealFilters {
  keyword?: string
  customer_id?: string
  partner_id?: string
  /** 담당자 사용자 id(UUID). */
  owner_user_id?: string
  vendor?: string
  stage?: DealStage
  revenue_from?: string
  revenue_to?: string
  /** true면 내가 담당자인 딜만.false는 쿼리에서 생략한다. */
  mine?: boolean
}

/** 빈 값(undefined·빈 문자열) 조건은 보내지 않는다. */
function clean(filters: DealFilters): DealFilters {
  return Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as DealFilters
}

export function useDeals(filters: DealFilters, offset: number) {
  const query = { ...clean(filters), offset, limit: PAGE_SIZE }
  return useQuery({
    queryKey: ['deals', query],
    queryFn: () => call(api.GET('/api/v1/deals', { params: { query } })),
  })
}

export function useDealPipeline({ mine = false }: { mine?: boolean } = {}) {
  const query = mine ? { mine: true } : {}
  return useQuery({
    queryKey: ['deal-pipeline', query],
    queryFn: () => call(api.GET('/api/v1/deals/pipeline', { params: { query } })),
  })
}

/** 단계 이력은 최근 이 건수만 요청한다(목록 PAGE_SIZE와 별개). */
export const STAGE_HISTORY_LIMIT = 50

export function useDealStageChanges(dealId: string, offset: number) {
  const query = { offset, limit: STAGE_HISTORY_LIMIT }
  return useQuery({
    queryKey: ['deal-stage-changes', dealId, query],
    queryFn: () =>
      call(api.GET('/api/v1/deals/{deal_id}/stage-changes', { params: { path: { deal_id: dealId }, query } })),
  })
}

export function useDeal(id: string) {
  return useQuery({
    queryKey: ['deal', id],
    queryFn: () => call(api.GET('/api/v1/deals/{deal_id}', { params: { path: { deal_id: id } } })),
  })
}

export function useSaveDeal() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: DealInput }) =>
      id
        ? call(api.PUT('/api/v1/deals/{deal_id}', { params: { path: { deal_id: id } }, body }))
        : call(api.POST('/api/v1/deals', { body })),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ['deals'] }),
        client.invalidateQueries({ queryKey: ['deal'] }),
        client.invalidateQueries({ queryKey: ['deal-pipeline'] }),
      ]),
  })
}

export function useChangeDealStage(dealId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: Schemas['DealStageChangeRequest']) =>
      call(api.POST('/api/v1/deals/{deal_id}/stage', { params: { path: { deal_id: dealId } }, body })),
    // 409(그 사이 다른 사용자가 변경)에도 화면이 서버 상태를 따라가도록 실패 시에도 무효화한다.
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ['deals'] }),
        client.invalidateQueries({ queryKey: ['deal'] }),
        client.invalidateQueries({ queryKey: ['deal-pipeline'] }),
        client.invalidateQueries({ queryKey: ['deal-stage-changes'] }),
      ]),
  })
}

export function useDeleteDeal() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      call(api.DELETE('/api/v1/deals/{deal_id}', { params: { path: { deal_id: id } } })),
    onSuccess: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ['deals'] }),
        client.invalidateQueries({ queryKey: ['deal-pipeline'] }),
      ]),
  })
}
