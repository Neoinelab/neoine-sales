import { api } from '../../shared/api/client'
import type { ContactsGateway } from '../types'
import { toContact, toContactBody, toContactRow } from './mappers/contact'
import { unwrap, unwrapVoid } from './request'

export function createContactsHttp(): ContactsGateway {
  return {
    companies: (kind) => unwrap(api.GET('/api/v1/contacts/companies', { params: { query: { kind } } })),
    byCompany: async (kind, company) =>
      (await unwrap(api.GET('/api/v1/contacts/by-company', { params: { query: { kind, company } } }))).map(toContactRow),
    list: async (query) => {
      // 지정하지 않은 조건은 보내지 않는다(서버 기본값을 쓴다).
      const params = {
        ...(query.kind ? { kind: query.kind } : {}),
        ...(query.keyword ? { keyword: query.keyword } : {}),
        ...(query.offset !== undefined ? { offset: query.offset } : {}),
        ...(query.limit !== undefined ? { limit: query.limit } : {}),
      }
      const page = await unwrap(api.GET('/api/v1/contacts', { params: { query: params } }))
      return { items: page.items.map(toContactRow), total: page.total, offset: page.offset, limit: page.limit }
    },
    create: async (kind, input) =>
      toContact(await unwrap(api.POST('/api/v1/contacts', { body: { kind, ...toContactBody(input) } }))),
    update: async (id, input) =>
      toContact(
        await unwrap(
          api.PUT('/api/v1/contacts/{contact_id}', { params: { path: { contact_id: id } }, body: toContactBody(input) }),
        ),
      ),
    remove: (id) => unwrapVoid(api.DELETE('/api/v1/contacts/{contact_id}', { params: { path: { contact_id: id } } })),
  }
}
