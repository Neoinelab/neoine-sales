import { useUpdateAction } from '../../../data/actions'
import { useActionTypes } from '../../../data/actionTypes'
import { useToday } from '../../../data/today'
import { canEditAction, type Viewer } from '../../../shared/model/permissions'
import type { DealAction, DealDetail, NextActionStatus } from '../../../shared/model/types'
import type { ActionUpdateInput } from '../../../shared/model/inputs'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Modal } from '../../../shared/ui/Modal'
import { useCommentWriting } from '../../../data/comments'
import { ActionComments } from './ActionComments'
import { ActionDetailFields } from './ActionDetailFields'
import { updateBody } from './actionEdit'
import { messageOf } from './detailHelpers'
import './detail.css'

export const NOTICE_EDIT = '본인 Action 또는 admin만 수정·삭제할 수 있습니다.'
export const NOTICE_DELETE_TITLE = '본인 Action 또는 admin만 삭제할 수 있습니다.'

interface ActionDetailDialogProps {
  deal: DealDetail
  action: DealAction
  canWrite: boolean
  me: Viewer | null
  /** 상태 변경·삭제 요청이 진행 중이다(닫기·삭제·상태 버튼을 끈다). */
  pending: boolean
  error: unknown
  onChangeStatus: (action: DealAction, status: NextActionStatus) => void
  onDelete: (action: DealAction) => void
  onNotice: (message: string) => void
  onClose: () => void
  /** 열릴 때 Comment 입력 칸에 포커스를 둔다(표의 Comment 아이콘으로 열었을 때). */
  focusComment?: boolean
}

/** Action 상세 팝업: 모든 항목을 보고, 권한이 있으면 칸별로 고치고 삭제한다. 저장 중에는 닫히지 않는다. */
export function ActionDetailDialog({ deal, action, canWrite, me, pending, error, onChangeStatus, onDelete, onNotice, onClose, focusComment = false }: ActionDetailDialogProps) {
  const update = useUpdateAction()
  const today = useToday().today
  const types = useActionTypes().data ?? []
  const own = canWrite && me !== null && canEditAction(me, action.actor.id)
  const writing = useCommentWriting()
  const busy = pending || update.isPending || writing

  async function save(patch: Partial<ActionUpdateInput>) {
    await update.mutateAsync({ dealCode: deal.code, actionId: action.id, input: updateBody(action, patch) })
    onNotice('Action이 수정되었습니다.')
  }

  return (
    <Modal
      className="dd-action-detail-modal"
      title="Action 상세"
      wide
      onClose={busy ? () => undefined : onClose}
      footer={
        <>
          {canWrite && (
            <button type="button" className="danger" disabled={!own || busy} title={own ? undefined : NOTICE_DELETE_TITLE} onClick={() => onDelete(action)}>
              삭제
            </button>
          )}
          <button type="button" disabled={busy} onClick={onClose}>
            닫기
          </button>
        </>
      }
    >
      {canWrite && !own && <p className="hint">{NOTICE_EDIT}</p>}
      <ActionDetailFields
        action={action}
        canEdit={own}
        today={today}
        registeredOn={deal.createdAt.slice(0, 10)}
        types={types}
        statusBusy={busy}
        saving={update.isPending}
        onChangeStatus={onChangeStatus}
        onSave={save}
      />
      <ErrorBanner error={error} format={messageOf} />
      <ActionComments deal={deal} action={action} canWrite={canWrite} me={me} focusInput={focusComment} />
    </Modal>
  )
}
