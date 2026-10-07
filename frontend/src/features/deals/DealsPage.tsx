import { useState } from 'react'
import { Link } from 'react-router'
import { PAGE_SIZE } from '../../shared/constants'
import { formatAmount } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Pager } from '../../shared/ui/Pager'
import { useCustomerOptions } from '../customers/hooks'
import { DealForm } from './DealForm'
import { useDeals, useDeleteDeal, type Deal } from './hooks'

type Editing = { kind: 'new' } | { kind: 'edit'; deal: Deal } | null

export function DealsPage() {
  const [offset, setOffset] = useState(0)
  const [editing, setEditing] = useState<Editing>(null)
  const deals = useDeals(offset)
  const customers = useCustomerOptions()
  const remove = useDeleteDeal()
  const items = deals.data?.items ?? []
  const customerName = new Map(customers.data?.items.map((c) => [c.id, c.company_name]))

  return (
    <section>
      <div className="heading">
        <h1>딜</h1>
        <button type="button" className="primary" onClick={() => setEditing({ kind: 'new' })}>
          딜 등록
        </button>
      </div>
      <ErrorBanner error={deals.error ?? remove.error} />
      {editing && (
        <DealForm
          key={editing.kind === 'edit' ? editing.deal.id : 'new'}
          initial={editing.kind === 'edit' ? editing.deal : undefined}
          onDone={() => setEditing(null)}
        />
      )}
      <table>
        <thead>
          <tr>
            <th>Deal Code</th>
            <th>Deal Name</th>
            <th>Owner</th>
            <th>Vendor</th>
            <th>Solution</th>
            <th>매출금액</th>
            <th>매출일</th>
            <th>고객</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((d) => (
            <tr key={d.id}>
              <td>
                <Link to={`/deals/${d.id}`}>{d.code}</Link>
              </td>
              <td>{d.name}</td>
              <td>{d.owner}</td>
              <td>{d.vendor}</td>
              <td>{d.solution}</td>
              <td className="num">{formatAmount(d.revenue_amount, d.revenue_currency)}</td>
              <td>{d.revenue_date}</td>
              <td>{customerName.get(d.customer_id) ?? ''}</td>
              <td className="row-actions">
                <button type="button" onClick={() => setEditing({ kind: 'edit', deal: d })}>
                  수정
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (window.confirm(`${d.code} 딜을 삭제할까요?`)) remove.mutate(d.id)
                  }}
                >
                  삭제
                </button>
              </td>
            </tr>
          ))}
          {deals.isSuccess && items.length === 0 && (
            <tr>
              <td colSpan={9}>등록된 딜이 없습니다.</td>
            </tr>
          )}
        </tbody>
      </table>
      <Pager offset={offset} limit={PAGE_SIZE} count={items.length} onChange={setOffset} />
    </section>
  )
}
