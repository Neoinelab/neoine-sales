import { useState, type ReactNode } from 'react'
import { useContactsByCompany } from '../../../data/contacts'
import type { Contact, ContactDraft, ContactKind, ContactRow } from '../../../shared/model/types'
import type { ComboOption } from '../../../shared/ui/ComboBox'
import { ContactSession } from './ContactSession'
import { detailDraft, draftOf, EMPTY_DRAFT, isUnchanged, personDraft, sharedHint, type ContactChange } from './contactInline'
import { InlineEdit } from './InlineEdit'

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
  ['company', '회사'],
  ['person', '담당자'],
  ['title', '직급'],
  ['email', '이메일'],
  ['phone', '전화'],
] as const
type ContactField = (typeof CONTACT_FIELDS)[number][0]

const personOption = (row: ContactRow): ComboOption => ({
  id: row.id,
  value: row.name,
  description: [row.title, row.email].filter(Boolean).join(' · ') || undefined,
})

/**
 * 연락처 한 블록(회사·담당자·직급·이메일·전화)을 값 클릭으로 고친다.
 * 회사명 클릭 = 회사 pulldown 세션(ContactSession), 담당자명 = 같은 회사 담당자 pulldown(자동완성·신규 직접 입력),
 * 직급·이메일·전화 = 한 칸씩. 파트너가 없으면 같은 5행을 '—'로 보여 주고 아무 값이나 클릭해 추가 세션을 연다.
 */
export function InlineContactBlock({ kind, label, noun, contact, canWrite, sessionHint, onSave }: InlineContactBlockProps) {
  const [session, setSession] = useState(false)
  const rows = useContactsByCompany(kind, contact?.company ?? '').data ?? []

  async function saveSession(draft: ContactDraft) {
    await onSave(draft, 'session')
    setSession(false)
  }

  async function saveDraft(draft: ContactDraft, change: ContactChange) {
    if (contact && isUnchanged(contact, draft)) return
    await onSave(draft, change)
  }

  if (session) {
    return (
      <ContactSession
        kind={kind}
        label={label}
        noun={noun}
        initial={contact ? draftOf(contact) : EMPTY_DRAFT}
        linkedHere={contact !== null}
        hint={sessionHint}
        onSave={saveSession}
        onCancel={() => setSession(false)}
      />
    )
  }
  if (!contact) {
    const empty = (name: string) =>
      canWrite ? (
        <button type="button" className="dd-click" aria-label={`${label} ${name} 입력`} onClick={() => setSession(true)}>
          —
        </button>
      ) : (
        <span className="kv-static">—</span>
      )
    return <KvGrid values={(_field, name) => empty(name)} />
  }

  const shared = sharedHint(rows, contact)
  const detail = (field: 'title' | 'email' | 'phone', name: string, value: string | null) => (
    <InlineEdit
      label={`${label} ${name}`}
      canEdit={canWrite}
      noSpace={field !== 'title'}
      display={value || '—'}
      initial={value ?? ''}
      hint={shared}
      onSave={(text) => saveDraft(detailDraft(contact, field, text), 'detail')}
    />
  )

  const values: Record<ContactField, ReactNode> = {
    company: canWrite ? (
      <button type="button" className="dd-click" aria-label={`${label} 회사명 수정`} onClick={() => setSession(true)}>
        {contact.company}
      </button>
    ) : (
      <span className="kv-static">{contact.company}</span>
    ),
    person: (
      <InlineEdit
        label={`${label} 담당자명`}
        canEdit={canWrite}
        kind="combo"
        noSpace
        options={rows.map(personOption)}
        display={contact.name}
        initial={contact.name}
        onSave={(text, option) => saveDraft(personDraft(rows, contact, text, option?.id), 'person')}
      />
    ),
    title: detail('title', '직급', contact.title),
    email: detail('email', '이메일', contact.email),
    phone: detail('phone', '전화', contact.phone),
  }
  return <KvGrid values={(field) => values[field]} />
}

/** CONTACT_FIELDS 순서대로 행을 그린다. 각 행의 값은 `values(필드, 이름)`이 정한다. */
function KvGrid({ values }: { values: (field: ContactField, name: string) => ReactNode }) {
  return (
    <dl className="kv-grid">
      {CONTACT_FIELDS.map(([field, name]) => (
        <div key={field} className="kv-row">
          <dt>{name}</dt>
          <dd>{values(field, name)}</dd>
        </div>
      ))}
    </dl>
  )
}
