import { useState } from 'react'
import { PAGE_SIZE } from '../../shared/constants'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { KeywordSearchBar } from '../../shared/ui/KeywordSearchBar'
import { Pager } from '../../shared/ui/Pager'
import { usePermissions } from '../auth/hooks'
import { PartnerForm } from './PartnerForm'
import { usePartners, useDeletePartner, type Partner, type PartnerFilters } from './hooks'

type Editing = { kind: 'new' } | { kind: 'edit'; partner: Partner } | null

export function PartnersPage() {
  const { canWrite } = usePermissions()
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState<PartnerFilters>({})
  const [editing, setEditing] = useState<Editing>(null)
  const partners = usePartners(filters, offset)
  const remove = useDeletePartner()
  const searching = !!filters.keyword
  const items = partners.data?.items ?? []

  return (
    <section>
      <div className="heading">
        <h1>파트너</h1>
        {canWrite && (
          <button type="button" className="primary" onClick={() => setEditing({ kind: 'new' })}>
            파트너 등록
          </button>
        )}
      </div>
      <ErrorBanner error={partners.error ?? remove.error} />
      {canWrite && editing && (
        <PartnerForm
          key={editing.kind === 'edit' ? editing.partner.id : 'new'}
          initial={editing.kind === 'edit' ? editing.partner : undefined}
          onDone={() => setEditing(null)}
        />
      )}
      <KeywordSearchBar
        onSearch={(keyword) => {
          // 조건이 그대로면 쿼리 키가 같아 재조회되지 않으므로, 빈 폼 검색은 직접 다시 조회한다.
          if (!keyword && !searching && offset === 0) void partners.refetch()
          setFilters({ keyword })
          setOffset(0)
        }}
      />
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
                {canWrite && (
                  <>
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
                  </>
                )}
              </td>
            </tr>
          ))}
          {partners.isSuccess && items.length === 0 && (
            <tr>
              <td colSpan={6}>{searching ? '조건에 맞는 파트너가 없습니다.' : '등록된 파트너가 없습니다.'}</td>
            </tr>
          )}
        </tbody>
      </table>
      <Pager offset={offset} limit={PAGE_SIZE} count={items.length} onChange={setOffset} />
    </section>
  )
}
