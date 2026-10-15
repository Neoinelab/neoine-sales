import { useToday } from '../../../data/today'
import { formatDateTime } from '../../../shared/format'
import { userLabel } from '../../../shared/model/period'
import type { DealAction, DealDetail } from '../../../shared/model/types'
import { ForecastBadge, StatusBadge } from '../../../shared/ui/Badges'
import { RiskBadge } from '../../../shared/ui/RiskBadge'
import './detail.css'

interface ActionTableProps {
  actions: DealAction[]
  deal: DealDetail
  canEdit: boolean
  onEdit: (action: DealAction) => void
  onDelete: (action: DealAction) => void
}

/**
 * 현재 Next Action(= Deal의 가장 최근 Action)의 Due가 mock 시계의 오늘보다 지났는지.
 * 이미 다음 Action으로 넘어간 지난 Action의 Due는 표시만 한다. 종결 Deal(risk 없음)에는 붙이지 않는다.
 */
function isCurrentOverdue(action: DealAction, deal: DealDetail, today: string): boolean {
  const current = deal.nextAction
  if (deal.risk === null || current === null) return false
  return current.text === action.nextAction && current.dueDate === action.dueDate && action.dueDate < today
}

/** Actions 목록 표: 수행일시 / 담당자 / 등록 시점 Status·Forecast / 유형 / 진행사항 / Next Action / Due / Memo / 관리. */
export function ActionTable({ actions, deal, canEdit, onEdit, onDelete }: ActionTableProps) {
  const { today } = useToday()
  return (
    <div className="dd-scroll">
      <table className="dd-table" aria-label="Action 목록">
        <thead>
          <tr>
            <th>수행일시</th>
            <th>담당자</th>
            <th>등록 시점 Status·Forecast</th>
            <th>유형</th>
            <th>진행사항</th>
            <th>Next Action</th>
            <th>Due Date</th>
            <th>Memo</th>
            {canEdit && <th>관리</th>}
          </tr>
        </thead>
        <tbody>
          {actions.map((a) => (
            <tr key={a.id}>
              <td>{formatDateTime(a.actedAt)}</td>
              <td>{userLabel(a.actor)}</td>
              <td>
                <span className="dd-row">
                  <StatusBadge statusKey={a.statusKey} />
                  <ForecastBadge forecastKey={a.forecastKey} />
                </span>
              </td>
              <td>{a.type}</td>
              <td className="wrap">{a.progress}</td>
              <td className="wrap">{a.nextAction}</td>
              <td>
                <span className="dd-row">
                  <span>{a.dueDate}</span>
                  {isCurrentOverdue(a, deal, today) && <RiskBadge risk="overdue" />}
                </span>
              </td>
              <td className="wrap">{a.memo || '—'}</td>
              {canEdit && (
                <td>
                  <span className="dd-row">
                    <button type="button" className="dd-small" onClick={() => onEdit(a)}>
                      수정
                    </button>
                    <button type="button" className="dd-small" onClick={() => onDelete(a)}>
                      삭제
                    </button>
                  </span>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
