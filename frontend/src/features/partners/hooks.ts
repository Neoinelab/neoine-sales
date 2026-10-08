import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'
import { OPTIONS_LIMIT, PAGE_SIZE } from '../../shared/constants'

export type Partner = Schemas['PartnerResponse']
export type PartnerInput = Schemas['PartnerRequest']

export interface PartnerFilters {
  keyword?: string
}

/** 빈 값(undefined·빈 문자열) 조건은 보내지 않는다. */
function clean(filters: PartnerFilters): PartnerFilters {
  return Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as PartnerFilters
}

export function usePartners(filters: PartnerFilters, offset: number) {
  const query = { ...clean(filters), offset, limit: PAGE_SIZE }
  return useQuery({
    queryKey: ['partners', query],
    queryFn: () => call(api.GET('/api/v1/partners', { params: { query } })),
  })
}

export function usePartner(id: string) {
  return useQuery({
    queryKey: ['partner', id],
    queryFn: () =>
      call(api.GET('/api/v1/partners/{partner_id}', { params: { path: { partner_id: id } } })),
    enabled: !!id,
  })
}

/** 딜 화면의 선택 목록·이름 표시용(최대 200건). */
export function usePartnerOptions() {
  return useQuery({
    queryKey: ['partner-options'],
    queryFn: () =>
      call(api.GET('/api/v1/partners', { params: { query: { offset: 0, limit: OPTIONS_LIMIT } } })),
  })
}

export function useSavePartner() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: PartnerInput }) =>
      id
        ? call(api.PUT('/api/v1/partners/{partner_id}', { params: { path: { partner_id: id } }, body }))
        : call(api.POST('/api/v1/partners', { body })),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: ['partners'] }),
      client.invalidateQueries({ queryKey: ['partner'] }),
      client.invalidateQueries({ queryKey: ['partner-options'] }),
    ]),
  })
}

export function useDeletePartner() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      call(api.DELETE('/api/v1/partners/{partner_id}', { params: { path: { partner_id: id } } })),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: ['partners'] }),
      client.invalidateQueries({ queryKey: ['partner-options'] }),
    ]),
  })
}
