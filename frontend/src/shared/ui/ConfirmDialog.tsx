import type { ReactNode } from 'react'
import { Modal } from './Modal'

interface ConfirmDialogProps {
  title: string
  message: ReactNode
  confirmLabel?: string
  cancelLabel?: string
  /** 삭제 등 되돌릴 수 없는 동작: 확인 버튼을 빨강으로. */
  danger?: boolean
  /** 진행 중: 확인 버튼 비활성. */
  busy?: boolean
  /** 호출처 조건(예: Deal code 일치)이 충족될 때까지 확인 비활성. */
  confirmDisabled?: boolean
  /** 메시지 아래 추가 내용(입력란 등). */
  children?: ReactNode
  onConfirm: () => void
  onCancel: () => void
}

/** 확인/취소 대화상자. Esc는 취소. */
export function ConfirmDialog(props: ConfirmDialogProps) {
  const { title, message, confirmLabel = '확인', cancelLabel = '취소', danger = false, busy = false, confirmDisabled = false, children, onConfirm, onCancel } = props
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <button type="button" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button type="button" className={danger ? 'danger' : 'primary'} disabled={busy || confirmDisabled} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </>
      }
    >
      <div>{message}</div>
      {children}
    </Modal>
  )
}
