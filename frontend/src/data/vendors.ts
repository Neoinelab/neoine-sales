import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { Vendor } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.vendors.list. 키 keys.vendors. Deal 폼·상세·목록 필터와 관리 화면이 함께 쓴다. */
export function useVendors(): Query<Vendor[]> {
  return useQuery<Vendor[], ApiError>({ queryKey: keys.vendors, queryFn: () => gateway.vendors.list(), ...NO_RETRY })
}

/** gateway.vendors.create(name). 성공: keys.vendors 무효화. */
export function useCreateVendor(): Mutation<string, Vendor> {
  const invalidate = useInvalidate()
  return useMutation<Vendor, ApiError, string>({
    mutationFn: (name) => gateway.vendors.create(name),
    onSuccess: () => invalidate(keys.vendors),
  })
}

/** gateway.vendors.rename. 성공: keys.vendors + keys.deals 무효화(상세·목록의 이름 반영). */
export function useRenameVendor(): Mutation<{ id: number; name: string }, Vendor> {
  const invalidate = useInvalidate()
  return useMutation<Vendor, ApiError, { id: number; name: string }>({
    mutationFn: ({ id, name }) => gateway.vendors.rename(id, name),
    onSuccess: () => invalidate(keys.vendors, keys.deals),
  })
}

/** gateway.vendors.remove(id). 성공: keys.vendors 무효화. */
export function useRemoveVendor(): Mutation<number> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => gateway.vendors.remove(id),
    onSuccess: () => invalidate(keys.vendors),
  })
}
