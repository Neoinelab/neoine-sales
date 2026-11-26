import { useToday } from '../../../data/today'
import { canEditAction, type Viewer } from '../../../shared/model/permissions'
import { isOverdueRow } from '../../../shared/model/risk'
import { badgeText } from '../../../shared/model/commentBadge'
import type { ActionSortKey, DealAction, DealDetail, NextActionStatus } from '../../../shared/model/types'
import './comments.css'
import { RiskBadge } from '../../../shared/ui/RiskBadge'
import { SortableHeader } from '../../../shared/ui/SortableHeader'
import type { ActionSortState } from './actionSort'
import type { ActionUpdateInput } from '../../../shared/model/inputs'
import { ActionInlineField } from './ActionInlineField'
import { NextActionStatusCell } from './NextActionStatusCell'
import './detail.css'

interface ActionTableProps {
  actions: DealAction[]
  deal: DealDetail
  canEdit: boolean
  me: Viewer | null
  sort: ActionSortState
  onSort: (key: ActionSortKey) => void
  onOpen: (action: DealAction) => void
  /** 없으면 상태 변경 버튼을 보이지 않는다. */
  onChangeStatus?: (action: DealAction, status: NextActionStatus) => void
  statusBusy?: boolean
  /** Action id → 읽지 않은 Comment 수(없으면 0). */
  commentCounts?: Readonly<Record<number, number>>
  /** 없으면 Comment 열의 아이콘 버튼을 보이지 않는다. 누르면 그 Action의 상세 팝업을 Comment 입력 칸에 포커스를 둔 채 연다. */
  onOpenComment?: (action: DealAction) => void
  onSave?: (action: DealAction, patch: Partial<ActionUpdateInput>) => Promise<void>
  saving?: boolean
}

/** 서버 risk가 기한초과이고, 이 행의 Next Action이 Open이며 Due가 앱 시계의 오늘보다 앞이면 true. */
function isOverdueAction(action: DealAction, deal: DealDetail, today: string): boolean {
  if (deal.risk !== 'overdue' && deal.risk !== 'overdue_stale') return false
  return isOverdueRow(action.nextActionStatus, action.dueDate, today)
}

const noop = () => undefined

/** Comment 열의 아이콘 버튼: 쓰기 권한자는 "Comment 추가", user는 "Comment 보기". 읽지 않은 수가 있으면 이름 끝에 붙고 배지로도 보인다. */
function CommentButton({ unread, canWrite, onClick }: { unread: number; canWrite: boolean; onClick: () => void }) {
  const badge = badgeText(unread)
  const name = `${canWrite ? 'Comment 추가' : 'Comment 보기'}${badge === null ? '' : ` (읽지 않은 ${unread}건)`}`
  return (
    <button type="button" className="cm-icon-btn" aria-label={name} onClick={onClick}>
      <svg width="16" height="16" viewBox="0 0 20 20" aria-hidden="true" focusable="false">
        <path d="M3 4.5h14v9H9l-4 3v-3H3z" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      </svg>
      {badge !== null && <span className="cm-count">{badge}</span>}
    </button>
  )
}

export function ActionTable({ actions, deal, canEdit, me, sort, onSort, onOpen, onChangeStatus, statusBusy = false, commentCounts, onOpenComment, onSave, saving = false }: ActionTableProps) {
  const header = (label: string, key: ActionSortKey) => (
    <SortableHeader label={label} active={sort.sort === key} order={sort.order} onSort={() => onSort(key)} />
  )
  const { today } = useToday()
  const own = (a: DealAction) => me !== null && canEditAction(me, a.actor.id)
  return (
    <div className="dd-scroll dd-action-scroll">
      <table className="dd-table dd-action-table" aria-label="Action 목록">
        <thead>
          <tr>
            {header('수행일', 'actedAt')}
            {header('유형', 'type')}
            <SortableHeader label="진행사항" active={false} order={sort.order} />
            <SortableHeader label="Next Action" active={false} order={sort.order} />
            {header('Due Date', 'dueDate')}
            {header('상태', 'nextActionStatus')}
            <SortableHeader label="Comment" active={false} order={sort.order} />
          </tr>
        </thead>
        <tbody>
          {actions.map((a) => (
            <tr key={a.id} className="dd-action-row">
              <td className="dd-col-short">
                <a href={`?tab=actions&action=${a.id}`} onClick={(event) => { event.preventDefault(); onOpen(a) }}>{a.actedOn}</a>
              </td>
              <td className="dd-col-short">{a.type}</td>
              <td className="dd-col-long">
                {onSave ? <ActionInlineField action={a} field="progress" canEdit={canEdit && own(a)} saving={saving} onSave={(patch) => onSave(a, patch)} /> : (a.progress ?? '—')}
              </td>
              <td className="dd-col-long" id={`next-action-${a.id}`}>
                {onSave ? <ActionInlineField action={a} field="nextAction" canEdit={canEdit && own(a)} saving={saving} onSave={(patch) => onSave(a, patch)} /> : (a.nextAction ?? '—')}
              </td>
              <td className="dd-col-short">
                <div className="dd-row">
                  {onSave ? <ActionInlineField action={a} field="dueDate" canEdit={canEdit && own(a)} saving={saving} onSave={(patch) => onSave(a, patch)} /> : <span>{a.dueDate ?? '—'}</span>}
                  {isOverdueAction(a, deal, today) && <RiskBadge risk="overdue" />}
                </div>
              </td>
              <td className="dd-col-short">
                <NextActionStatusCell action={a} surface="table" canChange={canEdit && own(a) && onChangeStatus !== undefined} busy={statusBusy} describedBy={`next-action-${a.id}`} onChange={onChangeStatus ?? noop} />
              </td>
              <td className="dd-col-short">
                {onOpenComment && <CommentButton unread={commentCounts?.[a.id] ?? 0} canWrite={canEdit} onClick={() => onOpenComment(a)} />}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
