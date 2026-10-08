import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, type Schemas } from '../../shared/api/client'
import { call } from '../../shared/api/problem'
import { OPTIONS_LIMIT, PAGE_SIZE } from '../../shared/constants'

export type Customer = Schemas['CustomerResponse']
export type CustomerInput = Schemas['CustomerRequest']

export interface CustomerFilters {
  keyword?: string
}

/** 빈 값(undefined·빈 문자열) 조건은 보내지 않는다. */
function clean(filters: CustomerFilters): CustomerFilters {
  return Object.fromEntries(Object.entries(filters).filter(([, v]) => v)) as CustomerFilters
}

export function useCustomers(filters: CustomerFilters, offset: number) {
  const query = { ...clean(filters), offset, limit: PAGE_SIZE }
  return useQuery({
    queryKey: ['customers', query],
    queryFn: () => call(api.GET('/api/v1/customers', { params: { query } })),
  })
}

export function useCustomer(id: string) {
  return useQuery({
    queryKey: ['customer', id],
    queryFn: () =>
      call(api.GET('/api/v1/customers/{customer_id}', { params: { path: { customer_id: id } } })),
    enabled: !!id,
  })
}

/** 딜 화면의 선택 목록·이름 표시용(최대 200건). */
export function useCustomerOptions() {
  return useQuery({
    queryKey: ['customer-options'],
    queryFn: () =>
      call(api.GET('/api/v1/customers', { params: { query: { offset: 0, limit: OPTIONS_LIMIT } } })),
  })
}

export function useSaveCustomer() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: CustomerInput }) =>
      id
        ? call(api.PUT('/api/v1/customers/{customer_id}', { params: { path: { customer_id: id } }, body }))
        : call(api.POST('/api/v1/customers', { body })),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: ['customers'] }),
      client.invalidateQueries({ queryKey: ['customer'] }),
      client.invalidateQueries({ queryKey: ['customer-options'] }),
    ]),
  })
}

export function useDeleteCustomer() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      call(api.DELETE('/api/v1/customers/{customer_id}', { params: { path: { customer_id: id } } })),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: ['customers'] }),
      client.invalidateQueries({ queryKey: ['customer-options'] }),
    ]),
  })
}
