import { canEditAction, type Viewer } from '../../../shared/model/permissions'
import { badgeText } from '../../../shared/model/commentBadge'
import type { ActionSortKey, DealAction, DealDetail, NextActionStatus } from '../../../shared/model/types'
import './comments.css'
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
  /** 행을 눌렀을 때(상세 팝업 열기). */
  onOpen: (action: DealAction) => void
  /** 없으면 상태 변경 버튼을 보이지 않는다. */
  onChangeStatus?: (action: DealAction, status: NextActionStatus) => void
  statusBusy?: boolean
  /** Action id → 읽지 않은 Comment 수(없으면 0). */
  commentCounts?: Readonly<Record<number, number>>
  /** 없으면 Comment 열의 아이콘 버튼을 보이지 않는다. 누르면 그 Action의 상세 팝업을 Comment 입력 칸에 포커스를 둔 채 연다. */
  onOpenComment?: (action: DealAction) => void
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

/** 행 안의 버튼·링크·입력에서 온 이벤트는 행을 여는 동작으로 보지 않는다. */
const isInner = (target: EventTarget) => target instanceof Element && target.closest('button, a, input, select, textarea') !== null

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

/** Actions 목록 표: 수행일 / 유형 / 진행사항 / Next Action / Due Date / 상태 / Comment. 행을 누르면(Enter·Space 포함) 상세 팝업이 열린다. */
export function ActionTable({ actions, deal, canEdit, me, sort, onSort, onOpen, onChangeStatus, statusBusy = false, commentCounts, onOpenComment }: ActionTableProps) {
  const header = (label: string, key: ActionSortKey) => (
    <SortableHeader label={label} active={sort.sort === key} order={sort.order} onSort={() => onSort(key)} />
  )
  const own = (a: DealAction) => me !== null && canEditAction(me, a.actor.id)
  return (
    <div className="dd-scroll">
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
            // 행 전체가 "Action 상세" 팝업을 여는 버튼처럼 동작한다(키보드: Tab으로 닿고 Enter·Space로 연다).
            <tr
              key={a.id}
              className="dd-action-row"
              tabIndex={0}
              onClick={(e) => {
                if (!isInner(e.target)) onOpen(a)
              }}
              onKeyDown={(e) => {
                if (e.target !== e.currentTarget || (e.key !== 'Enter' && e.key !== ' ')) return
                e.preventDefault()
                onOpen(a)
              }}
            >
              <td className="dd-col-short">{a.actedOn}</td>
              <td className="dd-col-short">{a.type}</td>
              <td className="dd-col-long">{a.progress ?? '—'}</td>
              <td className="dd-col-long" id={`next-action-${a.id}`}>
                {a.nextAction ?? '—'}
              </td>
              <td className="dd-col-short">
                <span className="dd-row">
                  <span>{a.dueDate ?? '—'}</span>
                  {isCurrentOverdue(a, deal) && <RiskBadge risk="overdue" />}
                </span>
              </td>
              <td className="dd-col-short">
                <NextActionStatusCell action={a} canChange={canEdit && own(a) && onChangeStatus !== undefined} busy={statusBusy} describedBy={`next-action-${a.id}`} onChange={onChangeStatus ?? noop} />
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
