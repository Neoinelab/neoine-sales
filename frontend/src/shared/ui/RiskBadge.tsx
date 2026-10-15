import type { Risk } from '../model/types'
import './ui.css'

/** Risk 배지. 색만으로 구분하지 않도록 텍스트를 함께 둔다. null이면 아무것도 그리지 않는다. */
export function RiskBadge({ risk }: { risk: Risk }) {
  if (!risk) return null
  return (
    <>
      {(risk === 'overdue' || risk === 'overdue_stale') && <span className="badge risk-overdue">기한초과</span>}
      {(risk === 'stale' || risk === 'overdue_stale') && <span className="badge risk-stale">미업데이트</span>}
    </>
  )
}

/** 목록 행(tr)에 붙일 클래스. 기한초과가 우선(빨강), 미업데이트는 노랑. */
export function riskRowClass(risk: Risk): string {
  if (risk === 'overdue' || risk === 'overdue_stale') return 'risk-overdue'
  if (risk === 'stale') return 'risk-stale'
  return ''
}
