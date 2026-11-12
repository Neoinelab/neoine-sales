/** Deal 화면의 연락처 선택(ContactDraft) 처리: 먼저 검증·계획(planContact), 문제가 없을 때만 반영(commitContact). */

import { findSamePerson, validateContactInput, WHITESPACE_MESSAGE } from '../../../shared/model/contactRules'
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

/** 입력 정규화: title은 앞뒤 공백 제거, email은 소문자, 빈 email/phone은 null. company/name은 그대로(공백이 있으면 검증에서 거절). */
export function normalizeContact(input: ContactInput): ContactInput {
  return {
    company: input.company,
    name: input.name,
    title: input.title.trim(),
    email: input.email === null || input.email === '' ? null : input.email.toLowerCase(),
    phone: input.phone === null || input.phone === '' ? null : input.phone,
  }
}

const LIMITS = { company: 200, name: 100, title: 100 } as const
const NUL = '\u0000'
const LABELS = { company: '회사명', name: '담당자명', title: '직급', email: '이메일', phone: '전화번호' } as const

const nulMessage = (field: keyof typeof LABELS) => `${LABELS[field]}에는 NUL 문자를 쓸 수 없습니다`
const tooLong = (field: keyof typeof LIMITS) => `${LABELS[field]}은(는) ${LIMITS[field]}자를 넘을 수 없습니다`

/**
 * 규칙 위반이면 서버와 같은 순서의 첫 오류 문구로 422(CT-R6):
 * 공백(회사명·담당자명·이메일·전화) → 이메일(NUL·형식) → 전화(NUL·형식) → 회사명(NUL·빈 값·길이) → 담당자명 → 직급(NUL·길이).
 */
export function assertContactValid(input: ContactInput): void {
  const errors = validateContactInput(input)
  const whitespace = [errors.company, errors.name, errors.email, errors.phone].find((m) => m === WHITESPACE_MESSAGE)
  if (whitespace) throw validation(whitespace)
  if (input.email?.includes(NUL)) throw validation(nulMessage('email'))
  if (errors.email) throw validation(errors.email)
  if (input.phone?.includes(NUL)) throw validation(nulMessage('phone'))
  if (errors.phone) throw validation(errors.phone)
  for (const field of ['company', 'name'] as const) {
    if (input[field].includes(NUL)) throw validation(nulMessage(field))
    if (errors[field]) throw validation(errors[field] as string)
    if (Array.from(input[field]).length > LIMITS[field]) throw validation(tooLong(field))
  }
  if (input.title.includes(NUL)) throw validation(nulMessage('title'))
  if (Array.from(input.title).length > LIMITS.title) throw validation(tooLong('title'))
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
export function commitContact(ctx: MockContext, plan: ContactPlan, byId: number): number {
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
    // (Deal, 역할)마다 한 건: 같은 연락처를 고객과 파트너로 함께 쓰면 두 건, 비활성 파트너 링크도 센다(CT-R10).
    const roles = [
      ...(deal.customerContactId === plan.contact.id ? ['고객'] : []),
      ...(deal.partnerLinks.some((l) => l.contactId === plan.contact.id) ? ['파트너'] : []),
    ]
    for (const label of roles) {
      logHistory(ctx, deal.code, byId, 'contact', `${label} 연락처 정보 (${plan.contact.company} ${plan.contact.name})`, before, after)
    }
  }
  return plan.contact.id
}
