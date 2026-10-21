import type { ContactsGateway } from '../../../gateway/types'
import { DEAL_PAGE_SIZE } from '../../../shared/model/constants'
import { contactsOfCompany, distinctCompanies, findSamePerson } from '../../../shared/model/contactRules'
import type { Contact } from '../../../shared/model/types'
import { conflict, notFound } from '../errors'
import { takeId } from '../store'
import { clone, read, requireAdmin, requireUser, write, type MockContext } from './context'
import { assertContactValid, commitContact, DUPLICATE_CONTACT_MESSAGE, normalizeContact, planContact } from './contactPlan'
import { contactRow, dealsOfContact } from './views'

function find(ctx: MockContext, id: number): Contact {
  const found = ctx.store.data.contacts.find((c) => c.id === id)
  if (!found) throw notFound('연락처를 찾을 수 없습니다.')
  return found
}

export function createContactsGateway(ctx: MockContext): ContactsGateway {
  return {
    companies: (kind) =>
      read(ctx, () => {
        requireUser(ctx)
        return distinctCompanies(ctx.store.data.contacts, kind)
      }),
    byCompany: (kind, company) =>
      read(ctx, () => {
        requireUser(ctx)
        return contactsOfCompany(ctx.store.data.contacts, kind, company).map((c) => contactRow(ctx.store.data, c))
      }),
    list: (query) =>
      read(ctx, () => {
        requireAdmin(ctx)
        const needle = query.keyword?.trim().toLowerCase() ?? ''
        const rows = ctx.store.data.contacts
          .filter((c) => (query.kind ? c.kind === query.kind : true))
          .filter((c) => needle === '' || [c.company, c.name, c.email ?? ''].some((t) => t.toLowerCase().includes(needle)))
          .sort(
            (a, b) =>
              (a.kind === b.kind ? 0 : a.kind === 'customer' ? -1 : 1) ||
              a.company.localeCompare(b.company, 'ko') ||
              a.name.localeCompare(b.name, 'ko') ||
              a.id - b.id,
          )
        const offset = query.offset ?? 0
        const limit = query.limit ?? DEAL_PAGE_SIZE
        return { items: rows.slice(offset, offset + limit).map((c) => contactRow(ctx.store.data, c)), total: rows.length, offset, limit }
      }),
    create: (kind, input) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const next = normalizeContact(input)
        assertContactValid(next)
        const { data } = ctx.store
        if (findSamePerson(data.contacts, kind, next)) throw conflict(DUPLICATE_CONTACT_MESSAGE)
        const now = ctx.clock.now()
        const record: Contact = { id: takeId(data.counters, 'ct'), kind, ...next, createdAt: now, updatedAt: now }
        data.contacts.push(record)
        return clone(record)
      }),
    update: (id, input) =>
      write(ctx, () => {
        const admin = requireAdmin(ctx)
        const contact = find(ctx, id)
        const plan = planContact(ctx, contact.kind, { ...input, contactId: id })
        commitContact(ctx, plan, admin.id)
        return clone(contact)
      }),
    remove: (id) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const contact = find(ctx, id)
        const refs = dealsOfContact(ctx.store.data, id).length
        if (refs > 0) throw conflict(`연결된 Deal이 ${refs}건 있어 삭제할 수 없습니다.`)
        const { contacts } = ctx.store.data
        contacts.splice(contacts.indexOf(contact), 1)
      }),
  }
}
