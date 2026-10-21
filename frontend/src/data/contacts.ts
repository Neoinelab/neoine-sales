import { useMutation, useQuery } from '@tanstack/react-query'
import { gateway } from '../gateway'
import type { ApiError } from '../shared/api/problem'
import type { Contact, ContactInput, ContactKind, ContactListQuery, ContactRow, Page } from '../shared/model/types'
import { keys } from './queryKeys'
import { NO_RETRY, useInvalidate, type Mutation, type Query } from './result'

/** gateway.contacts.companies(kind). 키 keys.contactCompanies. ContactPicker 1단계. */
export function useContactCompanies(kind: ContactKind): Query<string[]> {
  return useQuery<string[], ApiError>({
    queryKey: keys.contactCompanies(kind),
    queryFn: () => gateway.contacts.companies(kind),
    ...NO_RETRY,
  })
}

/** gateway.contacts.byCompany(kind, company). company가 빈 문자열이면 비활성(data undefined). ContactPicker 2단계. */
export function useContactsByCompany(kind: ContactKind, company: string): Query<ContactRow[]> {
  return useQuery<ContactRow[], ApiError>({
    queryKey: keys.contactsByCompany(kind, company),
    queryFn: () => gateway.contacts.byCompany(kind, company),
    enabled: company !== '',
    ...NO_RETRY,
  })
}

/** gateway.contacts.list(query). 키 keys.contactList. admin contacts 관리. */
export function useContacts(query: ContactListQuery): Query<Page<ContactRow>> {
  return useQuery<Page<ContactRow>, ApiError>({
    queryKey: keys.contactList(query),
    queryFn: () => gateway.contacts.list(query),
    ...NO_RETRY,
  })
}

/** gateway.contacts.create(kind, input). 성공: keys.contacts 무효화. */
export function useCreateContact(): Mutation<{ kind: ContactKind; input: ContactInput }, Contact> {
  const invalidate = useInvalidate()
  return useMutation<Contact, ApiError, { kind: ContactKind; input: ContactInput }>({
    mutationFn: ({ kind, input }) => gateway.contacts.create(kind, input),
    onSuccess: () => invalidate(keys.contacts),
  })
}

/** gateway.contacts.update(id, input). 성공: keys.contacts + keys.deals + keys.historyAll 무효화. */
export function useUpdateContact(): Mutation<{ id: number; input: ContactInput }, Contact> {
  const invalidate = useInvalidate()
  return useMutation<Contact, ApiError, { id: number; input: ContactInput }>({
    mutationFn: ({ id, input }) => gateway.contacts.update(id, input),
    onSuccess: () => invalidate(keys.contacts, keys.deals, keys.historyAll),
  })
}

/** gateway.contacts.remove(id). 성공: keys.contacts 무효화. 참조 중이면 409(ApiError). */
export function useRemoveContact(): Mutation<number> {
  const invalidate = useInvalidate()
  return useMutation<void, ApiError, number>({
    mutationFn: (id) => gateway.contacts.remove(id),
    onSuccess: () => invalidate(keys.contacts),
  })
}
