import { useUpdateAction } from '../../../data/actions'
import { useActionTypes } from '../../../data/actionTypes'
import { useToday } from '../../../data/today'
import { canEditAction, type Viewer } from '../../../shared/model/permissions'
import type { DealAction, DealDetail, NextActionStatus } from '../../../shared/model/types'
import type { ActionUpdateInput } from '../../../shared/model/inputs'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { Modal } from '../../../shared/ui/Modal'
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
  /** 삭제·상태 되돌리기 같은 팝업 밖 동작의 오류(팝업 안에 보인다). */
  error: unknown
  onChangeStatus: (action: DealAction, status: NextActionStatus) => void
  onDelete: (action: DealAction) => void
  onNotice: (message: string) => void
  onClose: () => void
}

/** Action 상세 팝업: 모든 항목을 보고, 권한이 있으면 칸별로 고치고 삭제한다. 저장 중에는 닫히지 않는다. */
export function ActionDetailDialog({ deal, action, canWrite, me, pending, error, onChangeStatus, onDelete, onNotice, onClose }: ActionDetailDialogProps) {
  const update = useUpdateAction()
  const today = useToday().today
  const types = useActionTypes().data ?? []
  const own = canWrite && me !== null && canEditAction(me, action.actor.id)
  const busy = pending || update.isPending

  async function save(patch: Partial<ActionUpdateInput>) {
    await update.mutateAsync({ dealCode: deal.code, actionId: action.id, input: updateBody(action, patch) })
    onNotice('Action이 수정되었습니다.')
  }

  return (
    <Modal
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
        onChangeStatus={onChangeStatus}
        onSave={save}
      />
      <ErrorBanner error={error} format={messageOf} />
    </Modal>
  )
}
