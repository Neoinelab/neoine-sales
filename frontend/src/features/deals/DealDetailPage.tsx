import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { formatAmount } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { ActionList } from '../actions/ActionList'
import { DealForm } from './DealForm'
import { DealPartiesPanel } from './DealPartiesPanel'
import { useDeal } from './hooks'
import { StageChangeForm } from './StageChangeForm'
import { StageHistory } from './StageHistory'
import { STAGE_LABEL } from './stages'

export function DealDetailPage() {
  const { dealId = '' } = useParams()
  const deal = useDeal(dealId)
  const [editing, setEditing] = useState(false)

  if (deal.isPending) return <p>불러오는 중…</p>
  if (deal.isError) {
    return (
      <>
        <ErrorBanner error={deal.error} />
        <Link to="/deals">딜 목록으로</Link>
      </>
    )
  }
  const d = deal.data
  return (
    <section>
      <p>
        <Link to="/deals">← 딜 목록</Link>
      </p>
      <div className="heading">
        <h1>
          {d.code} · {d.name}
        </h1>
        {!editing && (
          <button type="button" onClick={() => setEditing(true)}>
            수정
          </button>
        )}
      </div>
      {editing && <DealForm initial={d} onDone={() => setEditing(false)} />}
      <dl className="summary">
        <dt>현재 단계</dt>
        <dd>{STAGE_LABEL[d.stage]}</dd>
        <dt>Owner</dt>
        <dd>{d.owner}</dd>
        <dt>Vendor</dt>
        <dd>{d.vendor}</dd>
        <dt>Solution</dt>
        <dd>{d.solution}</dd>
        <dt>매출금액</dt>
        <dd>{formatAmount(d.revenue_amount, d.revenue_currency)}</dd>
        <dt>매출일</dt>
        <dd>{d.revenue_date}</dd>
      </dl>
      <DealPartiesPanel customerId={d.customer_id} partnerId={d.partner_id ?? null} />
      <StageChangeForm deal={d} />
      <StageHistory dealId={d.id} />
      <ActionList dealId={d.id} />
    </section>
  )
}
