import { useEffect, useId, useRef, type ReactNode } from 'react'
import './ui.css'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

interface ModalProps {
  title: string
  /** Esc 또는 닫기 동작. 호출처가 상태를 바꿔 언마운트한다. */
  onClose: () => void
  children: ReactNode
  /** 버튼 영역(우측 정렬). */
  footer?: ReactNode
  wide?: boolean
}

/** 접근 가능한 모달 대화상자: role=dialog, aria-modal, 열 때 포커스 이동, Esc 닫기, Tab 순환, 닫을 때 포커스 복귀. */
export function Modal({ title, onClose, children, footer, wide = false }: ModalProps) {
  const titleId = useId()
  const dialogRef = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  })

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = dialogRef.current
    const first = dialog?.querySelector<HTMLElement>(FOCUSABLE)
    ;(first ?? dialog)?.focus()

    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.stopPropagation()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab' || !dialog) return
      const items = Array.from(dialog.querySelectorAll<HTMLElement>(FOCUSABLE))
      if (items.length === 0) {
        event.preventDefault()
        return
      }
      const firstItem = items[0]
      const lastItem = items[items.length - 1]
      if (!dialog.contains(document.activeElement)) {
        event.preventDefault()
        firstItem?.focus()
      } else if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault()
        lastItem?.focus()
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault()
        firstItem?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      opener?.focus()
    }
  }, [])

  return (
    <div className="modal-backdrop">
      <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} className={wide ? 'modal wide' : 'modal'}>
        <h2 id={titleId}>{title}</h2>
        {children}
        {footer && <div className="modal-actions">{footer}</div>}
      </div>
    </div>
  )
}
