import { useState, type ReactNode } from 'react'
import type { Contact, ContactDraft, ContactKind } from '../../../shared/model/types'
import { ContactSession, type ContactFocusField } from './ContactSession'
import { draftOf, EMPTY_DRAFT, type ContactChange } from './contactInline'

interface InlineContactBlockProps {
  kind: ContactKind
  /** '고객' | '파트너'. */
  label: string
  /** 신규 회사 안내에 쓰는 이름('고객사' | '파트너'). */
  noun: string
  /** 현재 연락처. 파트너가 없으면 null. */
  contact: Contact | null
  canWrite: boolean
  /** 회사명 클릭 편집(세션) 위에 보이는 안내. */
  sessionHint?: string
  onSave: (draft: ContactDraft, change: ContactChange) => Promise<void>
}

/** 카드의 행 목록(순서·이름). 연락처가 있을 때와 없을 때 모두 이 목록으로 그린다. */
const CONTACT_FIELDS = [
  ['company', '회사', '회사명', 'Company'],
  ['person', '담당자', '담당자명', 'Name'],
  ['title', '직급', '직급', 'Title'],
  ['email', '이메일', '이메일', 'Email'],
  ['phone', '전화', '전화', 'Phone'],
] as const
type ContactField = (typeof CONTACT_FIELDS)[number][0]

/**
 * 연락처 한 블록(회사·담당자·직급·이메일·전화). 어느 값을 눌러도 같은 편집 세션(ContactSession, 5칸)이 열리고 누른 칸에 포커스가 간다.
 * 파트너가 없으면 같은 5행을 '—'로 보여 주고 아무 값이나 눌러 회사명부터 추가한다.
 */
export function InlineContactBlock({ kind, label, noun, contact, canWrite, sessionHint, onSave }: InlineContactBlockProps) {
  const [session, setSession] = useState<ContactFocusField | null>(null)

  async function saveSession(draft: ContactDraft, change: ContactChange) {
    await onSave(draft, change)
    setSession(null)
  }

  if (session) {
    const early = session === 'Company' || session === 'Name'
    return (
      <ContactSession
        kind={kind}
        label={label}
        noun={noun}
        initial={contact ? draftOf(contact) : EMPTY_DRAFT}
        linkedHere={contact !== null}
        hint={sessionHint}
        hintWhen={contact === null || early ? 'always' : 'changed'}
        focusField={session}
        onSave={saveSession}
        onCancel={() => setSession(null)}
      />
    )
  }
  if (!contact) {
    return (
      <KvGrid
        values={(_field, name) =>
          canWrite ? (
            <button type="button" className="dd-click" aria-label={`${label} ${name} 입력`} onClick={() => setSession('Company')}>
              —
            </button>
          ) : (
            <span className="kv-static">—</span>
          )
        }
      />
    )
  }

  const text: Record<ContactField, string> = {
    company: contact.company,
    person: contact.name,
    title: contact.title,
    email: contact.email ?? '',
    phone: contact.phone ?? '',
  }
  return (
    <KvGrid
      values={(field, _name, accessible, focus) =>
        canWrite ? (
          <button type="button" className="dd-click" aria-label={`${label} ${accessible} 수정`} onClick={() => setSession(focus)}>
            {text[field] || '—'}
          </button>
        ) : (
          <span className="kv-static">{text[field] || '—'}</span>
        )
      }
    />
  )
}

/** CONTACT_FIELDS 순서대로 행을 그린다. 각 행의 값은 `values(필드, 이름)`이 정한다. */
function KvGrid({ values }: { values: (field: ContactField, name: string, accessible: string, focus: ContactFocusField) => ReactNode }) {
  return (
    <dl className="kv-grid">
      {CONTACT_FIELDS.map(([field, name, accessible, focus]) => (
        <div key={field} className="kv-row">
          <dt>{name}</dt>
          <dd>{values(field, name, accessible, focus)}</dd>
        </div>
      ))}
    </dl>
  )
}
