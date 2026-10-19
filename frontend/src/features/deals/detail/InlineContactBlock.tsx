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

const personOption = (row: ContactRow): ComboOption => ({
  id: row.id,
  value: row.name,
  description: [row.title, row.email].filter(Boolean).join(' · ') || undefined,
})

/**
 * 연락처 한 블록(회사·담당자·직급·이메일·전화)을 값 클릭으로 고친다.
 * 회사명 클릭 = 회사 pulldown 세션(ContactSession), 담당자명 = 같은 회사 담당자 pulldown(자동완성·신규 직접 입력),
 * 직급·이메일·전화 = 한 칸씩. 파트너가 없으면 '없음' 값을 클릭해 추가한다.
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
    return (
      <p className="hint">
        {canWrite ? (
          <button type="button" className="dd-click" aria-label={`${label} 추가`} onClick={() => setSession(true)}>
            {label} 없음
          </button>
        ) : (
          `${label} 없음`
        )}
      </p>
    )
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

  const fields: Array<[string, ReactNode]> = [
    [
      '회사',
      canWrite ? (
        <button type="button" className="dd-click" aria-label={`${label} 회사명 수정`} onClick={() => setSession(true)}>
          {contact.company}
        </button>
      ) : (
        <span className="kv-static">{contact.company}</span>
      ),
    ],
    [
      '담당자',
      <InlineEdit
        label={`${label} 담당자명`}
        canEdit={canWrite}
        kind="combo"
        noSpace
        options={rows.map(personOption)}
        display={contact.name}
        initial={contact.name}
        onSave={(text, option) => saveDraft(personDraft(rows, contact, text, option?.id), 'person')}
      />,
    ],
    ['직급', detail('title', '직급', contact.title)],
    ['이메일', detail('email', '이메일', contact.email)],
    ['전화', detail('phone', '전화', contact.phone)],
  ]
  return (
    <dl className="kv-grid">
      {fields.map(([name, value]) => (
        <div key={name} className="kv-row">
          <dt>{name}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  )
}
