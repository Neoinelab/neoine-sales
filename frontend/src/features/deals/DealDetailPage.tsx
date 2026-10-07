import { Link, useParams } from 'react-router'
import { formatAmount } from '../../shared/format'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { ActionList } from '../actions/ActionList'
import { useDeal } from './hooks'

export function DealDetailPage() {
  const { dealId = '' } = useParams()
  const deal = useDeal(dealId)

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
      <h1>
        {d.code} · {d.name}
      </h1>
      <dl className="summary">
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
      <ActionList dealId={d.id} />
    </section>
  )
}
