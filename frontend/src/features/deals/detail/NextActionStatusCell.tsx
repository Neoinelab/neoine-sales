import { NEXT_ACTION_STATUS_LABEL } from '../../../shared/model/nextActionStatus'
import type { DealAction, NextActionStatus } from '../../../shared/model/types'

interface NextActionStatusCellProps {
  action: DealAction
  /** 상태를 바꿀 수 있는 사람(작성자·admin)인지. 아니면 라벨만 보인다. */
  canChange: boolean
  busy: boolean
  /** 행의 Next Action 칸 id. 같은 이름의 버튼을 행별로 구분하도록 설명으로 연결한다(버튼 이름은 그대로). */
  describedBy?: string
  surface: 'table' | 'dialog'
  /** 종료(수행)·종료(미수행)(전환 포함)는 Comment 종료 대화상자를 거치고, Open으로는 바로 바꾼다. */
  onChange: (action: DealAction, status: NextActionStatus) => void
}

/** Actions 표의 상태 칸. Next Action이 없는 행은 상태도 버튼도 없다. */
export function NextActionStatusCell({ action, canChange, busy, describedBy, surface, onChange }: NextActionStatusCellProps) {
  const status = action.nextActionStatus
  if (status === null) return <>—</>
  const inDialog = surface === 'dialog'
  const button = (target: NextActionStatus, label: string) => (
    <button type="button" className="dd-small" disabled={busy} aria-describedby={describedBy} onClick={() => onChange(action, target)}>
      {label}
    </button>
  )
  return (
    <span className="dd-row dd-next-action-status">
      <span>
        {NEXT_ACTION_STATUS_LABEL[status]}
        {inDialog && status !== 'open' && action.nextActionClosedOn ? ` · 종료일 ${action.nextActionClosedOn}` : ''}
      </span>
      {canChange && (inDialog ? status !== 'done' : status === 'open') && button('done', '종료(수행)')}
      {canChange && inDialog && status !== 'notDone' && button('notDone', '종료(미수행)')}
      {canChange && inDialog && status !== 'open' && button('open', 'Open으로')}
    </span>
  )
}
