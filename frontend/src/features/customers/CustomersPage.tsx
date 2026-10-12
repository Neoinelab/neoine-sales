import { useState } from 'react'
import { PAGE_SIZE } from '../../shared/constants'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { KeywordSearchBar } from '../../shared/ui/KeywordSearchBar'
import { Pager } from '../../shared/ui/Pager'
import { usePermissions } from '../auth/hooks'
import { CustomerForm } from './CustomerForm'
import { useCustomers, useDeleteCustomer, type Customer, type CustomerFilters } from './hooks'

type Editing = { kind: 'new' } | { kind: 'edit'; customer: Customer } | null

export function CustomersPage() {
  const { canWrite } = usePermissions()
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState<CustomerFilters>({})
  const [editing, setEditing] = useState<Editing>(null)
  const customers = useCustomers(filters, offset)
  const remove = useDeleteCustomer()
  const searching = !!filters.keyword
  const items = customers.data?.items ?? []

  return (
    <section>
      <div className="heading">
        <h1>고객</h1>
        {canWrite && (
          <button type="button" className="primary" onClick={() => setEditing({ kind: 'new' })}>
            고객 등록
          </button>
        )}
      </div>
      <ErrorBanner error={customers.error ?? remove.error} />
      {canWrite && editing && (
        <CustomerForm
          key={editing.kind === 'edit' ? editing.customer.id : 'new'}
          initial={editing.kind === 'edit' ? editing.customer : undefined}
          onDone={() => setEditing(null)}
        />
      )}
      <KeywordSearchBar
        onSearch={(keyword) => {
          // 조건이 그대로면 쿼리 키가 같아 재조회되지 않으므로, 빈 폼 검색은 직접 다시 조회한다.
          if (!keyword && !searching && offset === 0) void customers.refetch()
          setFilters({ keyword })
          setOffset(0)
        }}
      />
      <table>
        <thead>
          <tr>
            <th>회사명</th>
            <th>담당자</th>
            <th>직함</th>
            <th>이메일</th>
            <th>전화번호</th>
            <th>직원수</th>
            <th>비고</th>
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
              <td>{c.employee_count}</td>
              <td>{c.notes}</td>
              <td className="row-actions">
                {canWrite && (
                  <>
                <button type="button" onClick={() => setEditing({ kind: 'edit', customer: c })}>
                  수정
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`${c.company_name} 고객을 삭제할까요?`)) remove.mutate(c.id)
                  }}
                >
                  삭제
                </button>
                  </>
                )}
              </td>
            </tr>
          ))}
          {customers.isSuccess && items.length === 0 && (
            <tr>
              <td colSpan={8}>{searching ? '조건에 맞는 고객이 없습니다.' : '등록된 고객이 없습니다.'}</td>
            </tr>
          )}
        </tbody>
      </table>
      <Pager offset={offset} limit={PAGE_SIZE} count={items.length} onChange={setOffset} />
    </section>
  )
}
