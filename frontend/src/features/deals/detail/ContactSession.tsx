import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent } from 'react'
import { useContactCompanies } from '../../../data/contacts'
import { ContactPicker } from '../../../shared/contact/ContactPicker'
import { normalizeName, validateContactInput, type ContactFieldErrors } from '../../../shared/model/contactRules'
import type { ContactDraft, ContactKind } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { messageOf } from './detailHelpers'

interface ContactSessionProps {
  kind: ContactKind
  /** '고객' | '파트너'. 입력 라벨 접두어. */
  label: string
  /** 신규 회사 안내에 쓰는 이름('고객사' | '파트너'). */
  noun: string
  initial: ContactDraft
  /** 이 연락처가 이미 이 Deal에 연결돼 있으면 true(공유 안내 기준). */
  linkedHere: boolean
  hint?: string
  /** 저장. 성공하면 호출처가 세션을 닫는다. */
  onSave: (draft: ContactDraft) => Promise<void>
  onCancel: () => void
}

function sameDraft(a: ContactDraft, b: ContactDraft): boolean {
  return a.contactId === b.contactId && a.company === b.company && a.name === b.name && a.title === b.title && a.email === b.email && a.phone === b.phone
}

/**
 * 회사명을 클릭해 시작하는 연락처 블록 편집(저장·취소 버튼 없음). 회사명 pulldown(자동완성) → 담당자 pulldown → 연락 정보 자동 채움.
 * 목록에 없는 회사를 입력하면 신규 회사로 보고 담당자 정보를 모두 비운다(ContactPicker 규칙).
 * 담당자를 목록에서 고르면 바로 저장한다. 직접 입력은 Enter(회사명에서는 담당자명으로 이동) 또는 블록 밖으로 포커스를 옮길 때 저장하며,
 * 회사명·담당자명이 비어 있으면 저장하지 않고 오류를 보이며 편집을 유지한다. Esc = 입력을 버리고 닫기.
 */
export function ContactSession({ kind, label, noun, initial, linkedHere, hint, onSave, onCancel }: ContactSessionProps) {
  const companies = useContactCompanies(kind).data
  const [draft, setDraft] = useState<ContactDraft>(initial)
  const [errors, setErrors] = useState<ContactFieldErrors>({})
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const [nameFocus, setNameFocus] = useState(0)
  const rootRef = useRef<HTMLDivElement>(null)
  const skipBlur = useRef(false)

  const inputOf = (field: 'Company' | 'Name') => rootRef.current?.querySelector<HTMLInputElement>(`input[name="${kind}${field}"]`)
  useEffect(() => inputOf('Company')?.focus(), []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (nameFocus > 0) inputOf('Name')?.focus()
  }, [nameFocus]) // eslint-disable-line react-hooks/exhaustive-deps

  const isNew = companies !== undefined && draft.company !== '' && !companies.some((c) => normalizeName(c) === normalizeName(draft.company))

  async function save(target: ContactDraft) {
    if (busy) return
    const cleaned: ContactDraft = {
      ...target,
      title: target.title.trim(),
      email: target.email === '' ? null : target.email,
      phone: target.phone === '' ? null : target.phone,
    }
    const found = validateContactInput(cleaned)
    setErrors(found)
    if (Object.keys(found).length > 0) return
    setBusy(true)
    setError(null)
    try {
      await onSave(cleaned)
      skipBlur.current = true
    } catch (caught) {
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  function cancel() {
    skipBlur.current = true
    onCancel()
  }

  function onKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.defaultPrevented) return
    if (event.key === 'Escape') {
      event.stopPropagation()
      cancel()
    } else if (event.key === 'Enter') {
      event.preventDefault()
      if (event.target === inputOf('Company') && draft.company !== '') setNameFocus((n) => n + 1)
      else void save(draft)
    }
  }

  function onBlur(event: FocusEvent<HTMLElement>) {
    if (skipBlur.current || busy) return
    if (event.relatedTarget instanceof Node && event.currentTarget.contains(event.relatedTarget)) return
    if (sameDraft(draft, initial)) cancel()
    else void save(draft)
  }

  return (
    // 입력기 안의 Enter/Esc/blur를 한 곳에서 처리한다(그룹 자체는 포커스를 받지 않는다).
    // eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions
    <div role="group" aria-label={`${label} 연락처 편집`} className="dd-bant" ref={rootRef} onKeyDown={onKeyDown} onBlur={onBlur}>
      {hint && <p className="hint">{hint}</p>}
      <ContactPicker
        kind={kind}
        label={label}
        value={draft}
        onChange={setDraft}
        errors={errors}
        linkedHere={linkedHere}
        onCompanySelect={() => setNameFocus((n) => n + 1)}
        onPersonSelect={(next) => void save(next)}
      />
      {isNew && <p className="field-hint">신규 {noun}입니다. 담당자 정보를 입력하세요.</p>}
      <ErrorBanner error={error} format={messageOf} />
    </div>
  )
}
