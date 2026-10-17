/** Deal 화면의 연락처 선택(ContactDraft) 처리: 먼저 검증·계획(planContact), 문제가 없을 때만 반영(commitContact). */

import { findSamePerson, validateContactInput } from '../../../shared/model/contactRules'
import type { Contact, ContactDraft, ContactInput, ContactKind } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId } from '../store'
import type { MockContext } from './context'
import { logHistory } from './historyLog'
import { dealsOfContact } from './views'

export const DUPLICATE_CONTACT_MESSAGE = '이미 등록된 연락처입니다.'

export type ContactPlan =
  | { type: 'existing'; contact: Contact; next: ContactInput; changed: boolean }
  | { type: 'new'; kind: ContactKind; next: ContactInput }

/** 입력 정규화: title은 앞뒤 공백 제거, 빈 email/phone은 null. company/name은 그대로(공백이 있으면 검증에서 거절). */
export function normalizeContact(input: ContactInput): ContactInput {
  return {
    company: input.company,
    name: input.name,
    title: input.title.trim(),
    email: input.email === null || input.email === '' ? null : input.email,
    phone: input.phone === null || input.phone === '' ? null : input.phone,
  }
}

/** 규칙 위반이면 첫 오류 문구로 422. */
export function assertContactValid(input: ContactInput): void {
  const errors = validateContactInput(input)
  const first = errors.company ?? errors.name ?? errors.email ?? errors.phone
  if (first) throw validation(first)
}

function sameFields(a: ContactInput, b: ContactInput): boolean {
  return a.company === b.company && a.name === b.name && a.title === b.title && a.email === b.email && a.phone === b.phone
}

export function planContact(ctx: MockContext, kind: ContactKind, draft: ContactDraft): ContactPlan {
  const next = normalizeContact(draft)
  assertContactValid(next)
  const { contacts } = ctx.store.data

  if (draft.contactId !== null) {
    const contact = contacts.find((c) => c.id === draft.contactId && c.kind === kind)
    if (!contact) throw notFound('연락처를 찾을 수 없습니다.')
    if (findSamePerson(contacts, kind, next, contact.id)) throw conflict(DUPLICATE_CONTACT_MESSAGE)
    return { type: 'existing', contact, next, changed: !sameFields(contact, next) }
  }

  const same = findSamePerson(contacts, kind, next)
  if (!same) return { type: 'new', kind, next }
  // 같은 사람으로 판정된 기존 연락처: 비어 있는 입력(이메일·전화·직급)은 기존 값을 지우지 않는다.
  const merged: ContactInput = {
    company: same.company,
    name: same.name,
    title: next.title === '' ? same.title : next.title,
    email: next.email ?? same.email,
    phone: next.phone ?? same.phone,
  }
  return { type: 'existing', contact: same, next: merged, changed: !sameFields(same, merged) }
}

function infoText(c: ContactInput): string {
  return `직급 ${c.title || '-'} · 이메일 ${c.email ?? '-'} · 전화 ${c.phone ?? '-'}`
}

/** 계획을 반영하고 연락처 id를 돌려준다. 갱신이면 그 연락처를 쓰는 모든 Deal에 History를 남기고 updatedAt을 갱신한다. */
export function commitContact(ctx: MockContext, plan: ContactPlan, byId: string): string {
  const { data } = ctx.store
  const now = ctx.clock.now()
  if (plan.type === 'new') {
    const record: Contact = { id: takeId(data.counters, 'ct'), kind: plan.kind, ...plan.next, createdAt: now, updatedAt: now }
    data.contacts.push(record)
    return record.id
  }
  if (!plan.changed) return plan.contact.id
  const before = infoText(plan.contact)
  Object.assign(plan.contact, plan.next, { updatedAt: now })
  const after = infoText(plan.contact)
  for (const deal of dealsOfContact(data, plan.contact.id)) {
    deal.updatedAt = now
    const label = deal.customerContactId === plan.contact.id ? '고객' : '파트너'
    logHistory(ctx, deal.code, byId, 'contact', `${label} 연락처 정보 (${plan.contact.company} ${plan.contact.name})`, before, after)
  }
  return plan.contact.id
}
