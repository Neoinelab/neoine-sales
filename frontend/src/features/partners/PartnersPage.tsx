import { useState } from 'react'
import { PAGE_SIZE } from '../../shared/constants'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Pager } from '../../shared/ui/Pager'
import { PartnerForm } from './PartnerForm'
import { usePartners, useDeletePartner, type Partner } from './hooks'

type Editing = { kind: 'new' } | { kind: 'edit'; partner: Partner } | null

export function PartnersPage() {
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<Editing>(null)
  const partners = usePartners(offset)
  const remove = useDeletePartner()
  const items = partners.data?.items ?? []

  return (
    <section>
      <div className="heading">
        <h1>파트너</h1>
        <button type="button" className="primary" onClick={() => setEditing({ kind: 'new' })}>
          파트너 등록
        </button>
      </div>
      <ErrorBanner error={partners.error ?? remove.error} />
      {editing && (
        <PartnerForm
          key={editing.kind === 'edit' ? editing.partner.id : 'new'}
          initial={editing.kind === 'edit' ? editing.partner : undefined}
          onDone={() => setEditing(null)}
        />
      )}
      <table>
        <thead>
          <tr>
            <th>파트너사</th>
            <th>담당자</th>
            <th>직함</th>
            <th>이메일</th>
            <th>전화번호</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.id}>
              <td>{c.company_name}</td>
              <td>{c.contact_name}</td>
              <td>{c.contact_title}</td>
              <td>{c.email}</td>
              <td>{c.phone}</td>
              <td className="row-actions">
                <button type="button" onClick={() => setEditing({ kind: 'edit', partner: c })}>
                  수정
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`${c.company_name} 파트너를 삭제할까요?`)) remove.mutate(c.id)
                  }}
                >
                  삭제
                </button>
              </td>
            </tr>
          ))}
          {partners.isSuccess && items.length === 0 && (
            <tr>
              <td colSpan={6}>등록된 파트너이 없습니다.</td>
            </tr>
          )}
        </tbody>
      </table>
      <Pager offset={offset} limit={PAGE_SIZE} count={items.length} onChange={setOffset} />
    </section>
  )
}
