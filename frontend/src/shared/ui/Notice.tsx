import type { ReactNode } from 'react'
import './ui.css'

interface NoticeProps {
  /** error는 role=alert, 나머지는 role=status. */
  kind?: 'info' | 'success' | 'warning' | 'error'
  /** 있으면 닫기 버튼을 둔다. */
  onClose?: () => void
  children: ReactNode
}

/** 알림 줄(저장 결과, 함께 바뀐 값, 안내). */
export function Notice({ kind = 'info', onClose, children }: NoticeProps) {
  return (
    <div role={kind === 'error' ? 'alert' : 'status'} className={`notice ${kind}`}>
      <span>{children}</span>
      {onClose && (
        <button type="button" aria-label="닫기" onClick={onClose}>
          ×
        </button>
      )}
    </div>
  )
}
