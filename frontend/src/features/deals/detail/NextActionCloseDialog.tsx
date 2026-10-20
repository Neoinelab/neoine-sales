import { useState } from 'react'
import { NEXT_ACTION_STATUS_LABEL } from '../../../shared/model/nextActionStatus'
import type { NextActionStatus } from '../../../shared/model/types'
import { ErrorBanner } from '../../../shared/ui/ErrorBanner'
import { messageOf } from './detailHelpers'
import { ConfirmDialog } from '../../../shared/ui/ConfirmDialog'

interface NextActionCloseDialogProps {
  /** 종료 상태(`done` 또는 `notDone`). */
  status: Exclude<NextActionStatus, 'open'>
  nextAction: string
  busy: boolean
  /** 서버가 거절한 이유(있으면 팝업 안에 알린다). */
  error?: unknown
  /** 입력한 Memo(비어 있어도 된다). */
  onConfirm: (memo: string) => void
  onCancel: () => void
}

/** Next Action 종료 팝업: Memo에 남길 내용을 받는다. "취소"와 Esc는 종료 자체를 취소한다. */
export function NextActionCloseDialog({ status, nextAction, busy, error, onConfirm, onCancel }: NextActionCloseDialogProps) {
  const [memo, setMemo] = useState('')
  return (
    <ConfirmDialog
      title={`Next Action ${NEXT_ACTION_STATUS_LABEL[status]}`}
      message={`"${nextAction}"을(를) ${NEXT_ACTION_STATUS_LABEL[status]}(으)로 종료합니다. 남길 내용이 없으면 비워 두세요.`}
      confirmLabel="종료"
      busy={busy}
      onConfirm={() => onConfirm(memo)}
      onCancel={onCancel}
    >
      <label className="field">
        <span>Memo에 남길 내용(선택)</span>
        <textarea value={memo} onChange={(e) => setMemo(e.target.value)} />
      </label>
      <ErrorBanner error={error} format={messageOf} />
    </ConfirmDialog>
  )
}
