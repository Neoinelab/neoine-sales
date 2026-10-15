import { useId, useState } from 'react'
import { useCreateContact, useUpdateContact } from '../../../data/contacts'
import { useWhitespaceGuard } from '../../../shared/contact/useWhitespaceGuard'
import { validateContactInput, WHITESPACE_MESSAGE, type ContactField, type ContactFieldErrors } from '../../../shared/model/contactRules'
import type { ContactInput, ContactKind, ContactRow } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { SelectField } from '../../../shared/ui/fields'

interface Props {
  /** 수정할 연락처. 없으면 등록. */
  contact: ContactRow | null
  /** 등록 후 / 수정 후 호출(목록 갱신은 훅이 한다). */
  onSaved: (message: string) => void
  onCancel: () => void
}

interface Values {
  kind: ContactKind
  company: string
  name: string
  title: string
  email: string
  phone: string
}

function initialValues(contact: ContactRow | null): Values {
  return {
    kind: contact?.kind ?? 'customer',
    company: contact?.company ?? '',
    name: contact?.name ?? '',
    title: contact?.title ?? '',
    email: contact?.email ?? '',
    phone: contact?.phone ?? '',
  }
}

function toInput(values: Values): ContactInput {
  return {
    company: values.company,
    name: values.name,
    title: values.title.trim(),
    email: values.email === '' ? null : values.email,
    phone: values.phone === '' ? null : values.phone,
  }
}

interface FieldProps {
  label: string
  field: ContactField | 'title'
  value: string
  type?: 'text' | 'email' | 'tel'
  error: string | undefined
  onChange: (value: string) => void
}

/** 오류·안내를 입력 아래에 붙이는 텍스트 입력. */
function Field({ label, field, value, type = 'text', error, onChange }: FieldProps) {
  const id = useId()
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={field}
        type={type}
        value={value}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(e) => onChange(e.target.value)}
      />
      {error && (
        <span id={`${id}-error`} role="alert" className="field-error">
          {error}
        </span>
      )}
    </div>
  )
}

/** contacts 관리의 단순 폼(ContactPicker 아님). 공백은 입력 즉시 제거하고, 제출 때 규칙을 다시 검사한다. */
export function ContactForm({ contact, onSaved, onCancel }: Props) {
  const create = useCreateContact()
  const update = useUpdateContact()
  const { flashed, guard } = useWhitespaceGuard()
  const [values, setValues] = useState<Values>(() => initialValues(contact))
  const [errors, setErrors] = useState<ContactFieldErrors>({})
  const editing = contact !== null
  const mutation = editing ? update : create

  function set<K extends keyof Values>(key: K, value: Values[K]) {
    setValues((prev) => ({ ...prev, [key]: value }))
    setErrors((prev) => ({ ...prev, [key]: undefined }))
  }

  function setGuarded(field: ContactField, raw: string) {
    set(field, guard(field, raw))
  }

  function submit() {
    const input = toInput(values)
    const found = validateContactInput(input)
    setErrors(found)
    if (Object.keys(found).length > 0) return
    if (contact) {
      update.mutate({ id: contact.id, input }, { onSuccess: () => onSaved('연락처를 수정했습니다.') })
    } else {
      create.mutate({ kind: values.kind, input }, { onSuccess: () => onSaved('연락처를 등록했습니다.') })
    }
  }

  const shown = (field: ContactField): string | undefined => (flashed[field] ? WHITESPACE_MESSAGE : errors[field])
  return (
    <form
      className="admin-card"
      aria-label={editing ? '연락처 수정' : '연락처 등록'}
      noValidate
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
    >
      <h3>{editing ? '연락처 수정' : '연락처 등록'}</h3>
      {contact && contact.dealCount > 0 && (
        <p className="hint">{`이 연락처를 쓰는 ${contact.dealCount}개 Deal에 모두 반영됩니다.`}</p>
      )}
      <ErrorBanner error={mutation.error} />
      <div className="admin-grid">
        {editing ? (
          <p className="field">
            <span className="muted">구분</span>
            <strong>{contact.kind === 'customer' ? '고객' : '파트너'}</strong>
          </p>
        ) : (
          <SelectField label="연락처 구분" name="kind" value={values.kind} onChange={(v) => set('kind', v as ContactKind)}>
            <option value="customer">고객</option>
            <option value="partner">파트너</option>
          </SelectField>
        )}
        <Field label="회사명" field="company" value={values.company} error={shown('company')} onChange={(v) => setGuarded('company', v)} />
        <Field label="담당자명" field="name" value={values.name} error={shown('name')} onChange={(v) => setGuarded('name', v)} />
        <Field label="직급" field="title" value={values.title} error={undefined} onChange={(v) => set('title', v)} />
        <Field label="이메일" field="email" type="email" value={values.email} error={shown('email')} onChange={(v) => setGuarded('email', v)} />
        <Field label="전화" field="phone" type="tel" value={values.phone} error={shown('phone')} onChange={(v) => setGuarded('phone', v)} />
      </div>
      <p className="hint">회사명·담당자명·이메일·전화에는 공백을 입력할 수 없습니다. 이메일은 없어도 됩니다.</p>
      <div className="actions">
        <button type="submit" className="primary" disabled={mutation.isPending}>
          저장
        </button>
        <button type="button" onClick={onCancel}>
          취소
        </button>
      </div>
    </form>
  )
}
