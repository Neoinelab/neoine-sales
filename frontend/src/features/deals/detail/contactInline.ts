/** 상세 연락처 인라인 편집의 순수 도우미(규칙은 shared/model/contactRules를 그대로 쓴다). */
import { normalizeName } from '../../../shared/model/contactRules'
import type { Contact, ContactDraft, ContactRow } from '../../../shared/model/types'

export const EMPTY_DRAFT: ContactDraft = { contactId: null, company: '', name: '', title: '', email: null, phone: null }

/** 한 블록 안에서 무엇을 바꿨는지. 알림 문구를 정하는 데 쓴다. */
export type ContactChange = 'session' | 'person' | 'detail'

export function draftOf(contact: Contact): ContactDraft {
  const { id, company, name, title, email, phone } = contact
  return { contactId: id, company, name, title, email, phone }
}

/** 기존 연락처 행을 고른 결과(연락 정보가 자동으로 채워진다). */
export function draftOfRow(row: ContactRow): ContactDraft {
  return draftOf(row)
}

/** 초안(세션 시작 값)과 현재 입력을 비교해 무엇이 바뀌었는지 답한다. 시작 값이 없으면 항상 연락처 변경. */
export function changeOfDraft(initial: ContactDraft | null, draft: ContactDraft): ContactChange | null {
  if (initial === null) return 'session'
  const same = initial.contactId === draft.contactId && initial.company === draft.company && initial.name === draft.name
  if (same && initial.title === draft.title && initial.email === draft.email && initial.phone === draft.phone) return null
  if (initial.contactId !== null && draft.contactId === initial.contactId) return 'detail'
  return normalizeName(initial.company) === normalizeName(draft.company) ? 'person' : 'session'
}

/** 현재 연락처(없으면 null)에 대한 저장 결과 구분: null 변경 없음 / detail 연락 정보 / person 담당자 / session 연락처 변경. */
export function contactChangeOf(contact: Contact | null, draft: ContactDraft): ContactChange | null {
  return changeOfDraft(contact ? draftOf(contact) : null, draft)
}

/**
 * 연결된 연락처가 없고 이메일이 비어 있으며 같은 회사에 같은 이름(대소문자 무시)의 담당자가 있으면 그 담당자의 연락 정보를 쓴다.
 * 그 밖에는 입력을 그대로 돌려준다. rows는 draft.company 기준 목록이다.
 */
export function resolveSamePerson(rows: readonly ContactRow[], draft: ContactDraft): ContactDraft {
  if (draft.contactId !== null || draft.email !== null) return draft
  const existing = rows.find((r) => normalizeName(r.name) === normalizeName(draft.name))
  return existing ? draftOfRow(existing) : draft
}
