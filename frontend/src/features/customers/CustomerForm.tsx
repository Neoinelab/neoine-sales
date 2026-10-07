import { useState } from 'react'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { TextArea, TextField } from '../../shared/ui/fields'
import { useSaveCustomer, type Customer } from './hooks'

interface Props {
  initial?: Customer
  onDone: () => void
}

export function CustomerForm({ initial, onDone }: Props) {
  const save = useSaveCustomer()
  const [form, setForm] = useState({
    company_name: initial?.company_name ?? '',
    contact_name: initial?.contact_name ?? '',
    contact_title: initial?.contact_title ?? '',
    email: initial?.email ?? '',
    phone: initial?.phone ?? '',
    employee_count: initial?.employee_count?.toString() ?? '',
    notes: initial?.notes ?? '',
  })
  const set = (key: keyof typeof form) => (value: string) => setForm((f) => ({ ...f, [key]: value }))

  return (
    <form
      className="panel"
      onSubmit={(e) => {
        e.preventDefault()
        save.mutate(
          {
            id: initial?.id,
            body: {
              ...form,
              employee_count: form.employee_count === '' ? null : Number(form.employee_count),
              contact_title: form.contact_title || null,
              email: form.email || null,
              phone: form.phone || null,
            },
          },
          { onSuccess: onDone },
        )
      }}
    >
      <h2>{initial ? '고객 수정' : '고객 등록'}</h2>
      <ErrorBanner error={save.error} />
      <TextField label="회사명" name="company_name" value={form.company_name} onChange={set('company_name')} required />
      <TextField label="담당자명" name="contact_name" value={form.contact_name} onChange={set('contact_name')} required />
      <TextField label="담당자 직함" name="contact_title" value={form.contact_title} onChange={set('contact_title')} />
      <TextField label="이메일" name="email" type="email" value={form.email} onChange={set('email')} />
      <TextField label="전화번호" name="phone" type="tel" value={form.phone} onChange={set('phone')} />
      <TextField label="직원수" name="employee_count" type="number" value={form.employee_count} onChange={set('employee_count')} />
      <TextArea label="비고" name="notes" value={form.notes} onChange={set('notes')} />
      <div className="actions">
        <button type="submit" className="primary" disabled={save.isPending}>
          저장
        </button>
        <button type="button" onClick={onDone}>
          취소
        </button>
      </div>
    </form>
  )
}
