/** 상세 연락처 인라인 편집의 순수 도우미(규칙은 shared/model/contactRules를 그대로 쓴다). */
import { validateContactInput, normalizeName } from '../../../shared/model/contactRules'
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

/**
 * 같은 회사 안에서 담당자명을 바꾼 결과. 목록에서 고른 사람(optionId) 또는 같은 이름(대소문자 무시)의 기존 담당자면
 * 그 연락 정보가 채워지고, 없는 이름이면 신규 담당자로 직급·이메일·전화는 비워 둔다.
 */
export function personDraft(rows: readonly ContactRow[], contact: Contact, typed: string, optionId?: string): ContactDraft {
  const name = typed.trim()
  if (name === '') throw new Error('담당자명을 입력하세요.')
  const existing = rows.find((r) => (optionId ? r.id === optionId : normalizeName(r.name) === normalizeName(name)))
  if (existing) return draftOfRow(existing)
  return { contactId: null, company: contact.company, name, title: '', email: null, phone: null }
}

/** 직급·이메일·전화 한 칸을 바꾼 결과. 형식 오류는 그 칸의 문구로 던진다. */
export function detailDraft(contact: Contact, field: 'title' | 'email' | 'phone', text: string): ContactDraft {
  const value = field === 'title' ? text.trim() : text
  const draft: ContactDraft = { ...draftOf(contact), [field]: field === 'title' ? value : value === '' ? null : value }
  const message = validateContactInput(draft)[field]
  if (message) throw new Error(message)
  return draft
}

export function isUnchanged(contact: Contact, draft: ContactDraft): boolean {
  const same = draftOf(contact)
  return (
    same.contactId === draft.contactId &&
    same.company === draft.company &&
    same.name === draft.name &&
    same.title === draft.title &&
    same.email === draft.email &&
    same.phone === draft.phone
  )
}

/** 여러 Deal이 함께 쓰는 연락처를 고칠 때의 안내(이 Deal 포함 2건 이상). */
export function sharedHint(rows: readonly ContactRow[], contact: Contact): string | undefined {
  const count = rows.find((r) => r.id === contact.id)?.dealCount ?? 0
  return count >= 2 ? `이 연락처는 ${count}개 Deal에서 함께 사용 중입니다. 수정하면 모두에 반영됩니다.` : undefined
}
