import { useState } from 'react'
import { NEXT_ACTION_STATUS_LABEL } from '../../../shared/model/nextActionStatus'
import type { NextActionStatus } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { messageOf } from './detailHelpers'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'

interface NextActionStatusDialogProps {
  status: NextActionStatus
  nextAction: string
  busy: boolean
  /** 서버가 거절한 이유(있으면 팝업 안에 알린다). */
  error?: unknown
  /** 입력한 Comment(비어 있어도 된다). */
  onConfirm: (comment: string) => void
  onCancel: () => void
}

export function NextActionStatusDialog({ status, nextAction, busy, error, onConfirm, onCancel }: NextActionStatusDialogProps) {
  const [comment, setComment] = useState('')
  const reopening = status === 'open'
  const change = reopening ? 'Open으로 되돌립니다' : `${NEXT_ACTION_STATUS_LABEL[status]}(으)로 종료합니다`
  return (
    <ConfirmDialog
      title={`Next Action ${NEXT_ACTION_STATUS_LABEL[status]}`}
      message={`"${nextAction}"을(를) ${change}. 남길 내용이 없으면 비워 두세요.`}
      confirmLabel={reopening ? 'Open으로' : '종료'}
      busy={busy}
      onConfirm={() => onConfirm(comment)}
      onCancel={onCancel}
    >
      <label className="field">
        <span>Comment에 남길 내용(선택)</span>
        <textarea value={comment} onChange={(e) => setComment(e.target.value)} />
      </label>
      <ErrorBanner error={error} format={messageOf} />
    </ConfirmDialog>
  )
}
