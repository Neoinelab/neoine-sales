import { useState } from 'react'
import { Link, useParams } from 'react-router'
import { useMe } from '../../../data/auth'
import { useDeal } from '../../../data/deals'
import { useLabels } from '../../../data/labels'
import '../../../shared/ui/kvGrid.css'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { useDealListPath } from '../../../shared/ui/useDealListPath'
import { DealForm } from './DealForm'
import './form.css'

/** Deal 등록(`/deals/new`)·수정(`/deals/:dealCode/edit`) 공용 화면(계획 6.4). 권한 가드는 App의 RequireWrite가 맡는다. */
export function DealFormPage() {
  const { dealCode } = useParams()
  const editing = dealCode !== undefined
  const me = useMe().data
  const deal = useDeal(dealCode)
  const labels = useLabels()
  const listPath = useDealListPath()
  // 폼이 마운트될 때 Label 조회가 다시 시작되어 pending으로 돌아가도 폼을 닫지 않도록, 처음 정해진 뒤에는 기억해 둔다.
  const [labelsSettled, setLabelsSettled] = useState(false)
  if (!labelsSettled && !labels.isPending) setLabelsSettled(true)

  if (editing && deal.error) {
    return (
      <div className="deal-form-page">
        <ErrorBanner error={deal.error} />
        <Link to={listPath}>목록으로</Link>
      </div>
    )
  }
  return (
    <div className="deal-form-page">
      <h1>{editing ? 'Deal 수정' : 'Deal 등록'}</h1>
      {/* 수정 폼은 BANT에 현재 Label 이름을 채우므로 Label 목록(성공 또는 실패)이 정해진 뒤에 연다. */}
      {!me || (editing && (!deal.data || !labelsSettled)) ? (
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
