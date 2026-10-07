import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'
import { PAGE_SIZE } from '../../shared/constants'

export type Deal = Schemas['DealResponse']
export type DealInput = Schemas['DealRequest']

export function useDeals(offset: number) {
  return useQuery({
    queryKey: ['deals', offset],
    queryFn: () => call(api.GET('/api/v1/deals', { params: { query: { offset, limit: PAGE_SIZE } } })),
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
      ]),
  })
}

export function useDeleteDeal() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      call(api.DELETE('/api/v1/deals/{deal_id}', { params: { path: { deal_id: id } } })),
    onSuccess: () => client.invalidateQueries({ queryKey: ['deals'] }),
  })
}
