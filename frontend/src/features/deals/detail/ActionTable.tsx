import { formatDateTime } from '../../../shared/format'
import { canEditAction, type Viewer } from '../../../shared/model/permissions'
import { userLabel } from '../../../shared/model/period'
import type { ActionSortKey, DealAction, DealDetail, NextActionStatus } from '../../../shared/model/types'
import { ForecastBadge, StatusBadge } from '../../../shared/ui/Badges'
import { RiskBadge } from '../../../shared/ui/RiskBadge'
import { SortableHeader } from '../../../shared/ui/SortableHeader'
import type { ActionSortState } from './actionSort'
import { NextActionStatusCell } from './NextActionStatusCell'
import './detail.css'

interface ActionTableProps {
  actions: DealAction[]
  deal: DealDetail
  canEdit: boolean
  me: Viewer | null
  sort: ActionSortState
  onSort: (key: ActionSortKey) => void
  onEdit: (action: DealAction) => void
  onDelete: (action: DealAction) => void
  /** 없으면 상태 변경 버튼을 보이지 않는다. */
  onChangeStatus?: (action: DealAction, status: NextActionStatus) => void
  statusBusy?: boolean
}

/**
 * 현재 Next Action(= Next Action이 있는 가장 최근 Action) 행인지. 기한초과 여부는 서버가 계산한 deal.risk를 따른다.
 * 그 뒤에 Next Action이 있는 Action이 더 생겼다면 지난 Action의 Due는 표시만 한다.
 */
function isCurrentOverdue(action: DealAction, deal: DealDetail): boolean {
  const current = deal.nextAction
  if (deal.risk !== 'overdue' && deal.risk !== 'overdue_stale') return false
  return current !== null && current.text === action.nextAction && current.dueDate === action.dueDate
}

const noop = () => undefined

/** Actions 목록 표: 수행일시 / 담당자 / 등록 시점 Status·Forecast / 유형 / 진행사항 / Next Action / Due / 상태 / Memo / 관리. */
export function ActionTable({ actions, deal, canEdit, me, sort, onSort, onEdit, onDelete, onChangeStatus, statusBusy = false }: ActionTableProps) {
  const header = (label: string, key: ActionSortKey) => (
    <SortableHeader label={label} active={sort.sort === key} order={sort.order} onSort={() => onSort(key)} />
  )
  const own = (a: DealAction) => me !== null && canEditAction(me, a.actor.id)
  return (
    <div className="dd-scroll">
      <table className="dd-table" aria-label="Action 목록">
        <thead>
          <tr>
            {header('수행일시', 'actedAt')}
            {header('담당자', 'actor')}
            <SortableHeader label="등록 시점 Status·Forecast" active={false} order={sort.order} />
            {header('유형', 'type')}
            <SortableHeader label="진행사항" active={false} order={sort.order} />
            <SortableHeader label="Next Action" active={false} order={sort.order} />
            {header('Due Date', 'dueDate')}
            {header('상태', 'nextActionStatus')}
            <SortableHeader label="Memo" active={false} order={sort.order} />
            {canEdit && <th scope="col">관리</th>}
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
              <td className="wrap">{a.progress ?? '—'}</td>
              <td className="wrap" id={`next-action-${a.id}`}>
                {a.nextAction ?? '—'}
              </td>
              <td>
                <span className="dd-row">
                  <span>{a.dueDate ?? '—'}</span>
                  {isCurrentOverdue(a, deal) && <RiskBadge risk="overdue" />}
                </span>
              </td>
              <td>
                <NextActionStatusCell action={a} canChange={canEdit && own(a) && onChangeStatus !== undefined} busy={statusBusy} describedBy={`next-action-${a.id}`} onChange={onChangeStatus ?? noop} />
              </td>
              <td className="wrap">{a.memo || '—'}</td>
              {canEdit && (
                <td>
                  <span className="dd-row">
                    <button
                      type="button"
                      className="dd-small"
                      disabled={!own(a)}
                      title={own(a) ? undefined : '본인 Action 또는 admin만 수정할 수 있습니다.'}
                      onClick={() => onEdit(a)}
                    >
                      수정
                    </button>
                    <button
                      type="button"
                      className="dd-small"
                      disabled={!own(a)}
                      title={own(a) ? undefined : '본인 Action 또는 admin만 삭제할 수 있습니다.'}
                      onClick={() => onDelete(a)}
                    >
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
