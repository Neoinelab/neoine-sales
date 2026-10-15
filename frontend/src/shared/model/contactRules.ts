/** 연락처 규칙(A-0 계약, 구현은 A-1). 화면(입력 차단·안내)과 게이트웨이(422/409)가 같은 함수를 쓴다. PRD 5.6 / 11.1. */

import type { ContactInput } from './inputs'
import type { Contact, ContactKind } from './types'

export const WHITESPACE_MESSAGE = '공백은 입력할 수 없습니다.'
export const EMAIL_FORMAT_MESSAGE = '이메일 형식이 올바르지 않습니다.'

export type ContactField = 'company' | 'name' | 'email' | 'phone'

/** 필드별 오류 문구. 오류가 없으면 빈 객체. */
export type ContactFieldErrors = Partial<Record<ContactField | 'title', string>>

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** 모든 공백 문자(스페이스·탭·전각 공백 등, `\s`)를 제거한다. 입력 차단·붙여넣기에 쓴다. */
export function stripWhitespace(text: string): string {
  return text.replace(/\s+/g, '')
}

export function hasWhitespace(text: string): boolean {
  return /\s/.test(text)
}

/**
 * 제출 검증.
 * - company/name: 비어 있으면 '회사명을 입력하세요.' / '담당자명을 입력하세요.'(게이트웨이용 일반 문구.
 *   Deal 폼은 "고객 회사명을 입력하세요." 같은 자체 문구를 쓰므로 이 필수 오류를 쓰지 않고 먼저 거른다).
 * - company/name/email/phone에 공백 문자가 있으면 WHITESPACE_MESSAGE.
 * - email이 null이 아니면 형식(`x@y.z`, 공백 없음)을 검사해 EMAIL_FORMAT_MESSAGE.
 * - title은 공백 허용이라 검증하지 않는다. email/phone의 빈 문자열은 허용하지 않는다(호출처가 null로 바꾼다).
 */
export function validateContactInput(input: ContactInput): ContactFieldErrors {
  const errors: ContactFieldErrors = {}
  if (input.company === '') errors.company = '회사명을 입력하세요.'
  else if (hasWhitespace(input.company)) errors.company = WHITESPACE_MESSAGE
  if (input.name === '') errors.name = '담당자명을 입력하세요.'
  else if (hasWhitespace(input.name)) errors.name = WHITESPACE_MESSAGE
  if (input.email !== null) {
    if (hasWhitespace(input.email)) errors.email = WHITESPACE_MESSAGE
    else if (!EMAIL_PATTERN.test(input.email)) errors.email = EMAIL_FORMAT_MESSAGE
  }
  if (input.phone !== null && hasWhitespace(input.phone)) errors.phone = WHITESPACE_MESSAGE
  return errors
}

/** 대소문자 무시 비교용 정규화(소문자). 회사명 distinct·같은 사람 판정에 쓴다. */
export function normalizeName(text: string): string {
  return text.toLowerCase()
}

function sameCompanyAndName(contact: Contact, candidate: ContactInput): boolean {
  return (
    normalizeName(contact.company) === normalizeName(candidate.company) &&
    normalizeName(contact.name) === normalizeName(candidate.name)
  )
}

function byId(a: Contact, b: Contact): number {
  return a.id.localeCompare(b.id)
}

/**
 * 같은 사람 판정. 같은 구분(kind) 안에서만 비교한다. 우선순위:
 * 1) company+name+email이 모두 같다(대소문자 무시) → 같은 사람
 * 2) candidate.email이 null이면 company+name이 같은 연락처 중 id가 가장 작은 것 → 같은 사람
 *    (PRD: 이메일 없이 입력하면 같은 회사명+담당자명의 기존 연락처와 같은 사람)
 * 3) candidate.email이 있고 company+name이 같지만 이메일이 다른 연락처:
 *    - 그 연락처의 email이 null이면 같은 사람(이메일을 채워 갱신)
 *    - email이 있으면 동명이인(새 행)
 * `excludeId`는 자기 자신을 제외한다. 없으면 null.
 */
export function findSamePerson(
  contacts: readonly Contact[],
  kind: ContactKind,
  candidate: ContactInput,
  excludeId?: string,
): Contact | null {
  const pool = contacts.filter((c) => c.kind === kind && c.id !== excludeId && sameCompanyAndName(c, candidate))
  if (candidate.email !== null) {
    const email = normalizeName(candidate.email)
    const exact = pool.filter((c) => c.email !== null && normalizeName(c.email) === email).sort(byId)[0]
    if (exact) return exact
    return pool.filter((c) => c.email === null).sort(byId)[0] ?? null
  }
  return [...pool].sort(byId)[0] ?? null
}

/**
 * 해당 구분의 회사명 distinct 목록. 대소문자만 다른 표기는 하나로 보고, 먼저 등록된 표기(createdAt, id 순)를
 * 대표로 쓴다. 결과는 가나다/알파벳 순(localeCompare 'ko').
 */
export function distinctCompanies(contacts: readonly Contact[], kind: ContactKind): string[] {
  const ordered = contacts
    .filter((c) => c.kind === kind)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt) || byId(a, b))
  const seen = new Map<string, string>()
  for (const c of ordered) {
    const key = normalizeName(c.company)
    if (!seen.has(key)) seen.set(key, c.company)
  }
  return [...seen.values()].sort((a, b) => a.localeCompare(b, 'ko'))
}

/** 회사명(대소문자 무시)으로 거른 담당자 목록, 이름 순. */
export function contactsOfCompany(
  contacts: readonly Contact[],
  kind: ContactKind,
  company: string,
): Contact[] {
  const key = normalizeName(company)
  return contacts
    .filter((c) => c.kind === kind && normalizeName(c.company) === key)
    .sort((a, b) => a.name.localeCompare(b.name, 'ko') || byId(a, b))
}
