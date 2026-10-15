import { useState } from 'react'
import { useContacts, useRemoveContact } from '../../../data/contacts'
import { DEAL_PAGE_SIZE } from '../../../shared/model/constants'
import type { ContactKind, ContactRow } from '../../../shared/model/types'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { SelectField } from '../../../shared/ui/fields'
import { KeywordSearchBar } from '../../../shared/ui/KeywordSearchBar'
import { Notice } from '../../../shared/ui/Notice'
import { Pager } from '../../../shared/ui/Pager'
import '../admin.css'
import { ContactForm } from './ContactForm'
import { ContactsTable } from './ContactsTable'

type KindFilter = ContactKind | ''

/** 고객·파트너 연락처 관리(`/admin/contacts`): 구분 필터, 키워드 검색, 등록·수정·삭제. */
export function ContactsPage() {
  const [kind, setKind] = useState<KindFilter>('')
  const [keyword, setKeyword] = useState<string | undefined>(undefined)
  const [offset, setOffset] = useState(0)
  const [form, setForm] = useState<{ contact: ContactRow | null } | null>(null)
  const [deleting, setDeleting] = useState<ContactRow | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const contacts = useContacts({ kind: kind || undefined, keyword, offset, limit: DEAL_PAGE_SIZE })
  const remove = useRemoveContact()

  function confirmDelete(row: ContactRow) {
    setMessage(null)
    remove.reset()
    remove.mutate(row.id, {
      onSuccess: () => setMessage(`${row.company} ${row.name} 연락처를 삭제했습니다.`),
      onSettled: () => setDeleting(null),
    })
  }

  const page = contacts.data
  return (
    <section className="admin-page" aria-labelledby="contacts-title">
      <div className="heading">
        <h2 id="contacts-title">contacts 관리</h2>
        <button
          type="button"
          className="primary"
          onClick={() => {
            setMessage(null)
            setForm({ contact: null })
          }}
        >
          연락처 등록
        </button>
      </div>
      <p className="hint">Deal에서 쓰는 고객·파트너 연락처(명함) 데이터입니다. 연결된 Deal이 있으면 삭제할 수 없습니다.</p>
      <ErrorBanner error={contacts.error ?? remove.error} />
      {message && (
        <Notice kind="success" onClose={() => setMessage(null)}>
          {message}
        </Notice>
      )}
      {form && (
        <ContactForm
          key={form.contact?.id ?? 'new'}
          contact={form.contact}
          onCancel={() => setForm(null)}
          onSaved={(text) => {
            setForm(null)
            setMessage(text)
          }}
        />
      )}
      <div className="admin-form-row">
        <SelectField
          label="구분"
          name="kind"
          value={kind}
          onChange={(v) => {
            setKind(v as KindFilter)
            setOffset(0)
          }}
        >
          <option value="">전체</option>
          <option value="customer">고객</option>
          <option value="partner">파트너</option>
        </SelectField>
        <KeywordSearchBar
          onSearch={(k) => {
            setKeyword(k)
            setOffset(0)
          }}
        />
      </div>
      {contacts.isPending && <p className="hint">불러오는 중…</p>}
      {page && (
        <>
          <ContactsTable
            rows={page.items}
            filtered={kind !== '' || keyword !== undefined}
            onEdit={(row) => {
              setMessage(null)
              setForm({ contact: row })
            }}
            onDelete={setDeleting}
          />
          {page.total > DEAL_PAGE_SIZE && <Pager offset={page.offset} limit={page.limit} total={page.total} onChange={setOffset} />}
        </>
      )}
      {deleting && (
        <ConfirmDialog
          title="연락처 삭제"
          confirmLabel="삭제"
          danger
          busy={remove.isPending}
          message={`${deleting.company} ${deleting.name} 연락처를 삭제할까요? 연결된 Deal이 있으면 삭제할 수 없습니다.`}
          onConfirm={() => confirmDelete(deleting)}
          onCancel={() => setDeleting(null)}
        />
      )}
    </section>
  )
}
