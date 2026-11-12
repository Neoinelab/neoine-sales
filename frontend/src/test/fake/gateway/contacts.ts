import type { ContactsGateway } from '../../../gateway/types'
import { findSamePerson } from '../../../shared/model/contactRules'
import type { Contact } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId } from '../store'
import { clone, read, requireAdmin, requireUser, write, type MockContext } from './context'
import { assertContactValid, commitContact, DUPLICATE_CONTACT_MESSAGE, normalizeContact, planContact } from './contactPlan'
import { companiesOf, compareForList, peopleOf } from './contactOrder'
import { contactRow, dealsOfContact } from './views'

/** 서버 기본 페이지 크기·상한·검색어 길이(CT-R13). */
const DEFAULT_LIMIT = 50
const MAX_LIMIT = 200
const KEYWORD_MAX = 100

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
        return companiesOf(ctx.store.data.contacts, kind)
      }),
    byCompany: (kind, company) =>
      read(ctx, () => {
        requireUser(ctx)
        return peopleOf(ctx.store.data.contacts, kind, company).map((c) => contactRow(ctx.store.data, c))
      }),
    list: (query) =>
      read(ctx, () => {
        requireAdmin(ctx)
        const raw = query.keyword ?? ''
        const keyword = raw.trim()
        const offset = query.offset ?? 0
        const limit = query.limit ?? DEFAULT_LIMIT
        if (Array.from(raw).length > KEYWORD_MAX || offset < 0 || limit < 1 || limit > MAX_LIMIT)
          throw validation('요청 형식이 올바르지 않습니다')
        if (keyword.includes('\u0000')) throw validation('검색어에는 NUL 문자를 쓸 수 없습니다')
        const needle = keyword.toLowerCase()
        const rows = ctx.store.data.contacts
          .filter((c) => (query.kind ? c.kind === query.kind : true))
          .filter((c) => needle === '' || [c.company, c.name, c.email ?? ''].some((t) => t.toLowerCase().includes(needle)))
          .sort(compareForList)
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
        assertContactValid(normalizeContact(input)) // 서버 판정 순서: 입력 검증 → 404 → 같은 사람 409
        const contact = find(ctx, id)
        const plan = planContact(ctx, contact.kind, { ...input, contactId: id })
        commitContact(ctx, plan, admin.id)
        contact.updatedAt = ctx.clock.now() // 값이 같아도 수정 시각은 갱신된다(CT-R9)
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
