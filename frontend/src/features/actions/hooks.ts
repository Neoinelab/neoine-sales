import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'
import { PAGE_SIZE } from '../../shared/constants'
import type { ActionType } from './labels'

export type DealAction = Schemas['DealActionResponse']
export type DealActionInput = Schemas['DealActionRequest']

export interface ActionFilters {
  action_type?: ActionType
  actor?: string
  keyword?: string
  acted_from?: string
  acted_to?: string
}

/** 빈 문자열 조건은 보내지 않는다. */
function clean(filters: ActionFilters): ActionFilters {
  return Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as ActionFilters
}

export function useActions(dealId: string | undefined, filters: ActionFilters, offset: number) {
  const query = { ...clean(filters), offset, limit: PAGE_SIZE }
  return useQuery({
    queryKey: ['actions', dealId ?? 'all', query],
    queryFn: () =>
      dealId
        ? call(
            api.GET('/api/v1/deals/{deal_id}/actions', {
              params: { path: { deal_id: dealId }, query },
            }),
          )
        : call(api.GET('/api/v1/deal-actions', { params: { query } })),
  })
}

export function useSaveAction(dealId: string) {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: DealActionInput }) =>
      id
        ? call(api.PUT('/api/v1/deal-actions/{action_id}', { params: { path: { action_id: id } }, body }))
        : call(
            api.POST('/api/v1/deals/{deal_id}/actions', {
              params: { path: { deal_id: dealId } },
              body,
            }),
          ),
    onSuccess: () => client.invalidateQueries({ queryKey: ['actions'] }),
  })
}

export function useDeleteAction() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      call(api.DELETE('/api/v1/deal-actions/{action_id}', { params: { path: { action_id: id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: ['actions'] }),
  })
}
