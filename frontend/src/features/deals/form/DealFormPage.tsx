import { Link, useParams } from 'react-router'
import { useMe } from '../../../data/auth'
import { useDeal } from '../../../data/deals'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { DealForm } from './DealForm'
import './form.css'

/** Deal 등록(`/deals/new`)·수정(`/deals/:dealCode/edit`) 공용 화면(계획 6.4). 권한 가드는 App의 RequireWrite가 맡는다. */
export function DealFormPage() {
  const { dealCode } = useParams()
  const editing = dealCode !== undefined
  const me = useMe().data
  const deal = useDeal(dealCode)

  if (editing && deal.error) {
    return (
      <div className="deal-form-page">
        <ErrorBanner error={deal.error} />
        <Link to="/deals">목록으로</Link>
      </div>
    )
  }
  return (
    <div className="deal-form-page">
      <h1>{editing ? 'Deal 수정' : 'Deal 등록'}</h1>
      {deal.data && <p className="hint">Deal code {deal.data.code}</p>}
      {!me || (editing && !deal.data) ? (
        <p className="hint">불러오는 중…</p>
      ) : (
        <DealForm
          key={deal.data?.code ?? 'new'}
          {...(deal.data ? { original: deal.data } : {})}
          defaultOwnerId={me.role === 'sales' ? me.id : ''}
        />
      )}
    </div>
  )
}
