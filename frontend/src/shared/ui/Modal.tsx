import { useEffect, useId, useRef, type ReactNode } from 'react'
import './ui.css'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** 열려 있는 Modal의 대화상자 요소(열린 순서). 겹친 Modal에서는 맨 위 Modal만 Esc·Tab을 처리한다. */
const openDialogs: HTMLElement[] = []

/** 다른 열린 Modal을 안에 품지 않은 것 중 가장 늦게 열린 것이 맨 위다(안쪽 Modal이 바깥 Modal의 DOM 안에 렌더돼도 안쪽이 위). */
function isTopDialog(dialog: HTMLElement): boolean {
  const candidates = openDialogs.filter((d) => !openDialogs.some((other) => other !== d && d.contains(other)))
  return candidates[candidates.length - 1] === dialog
}

interface ModalProps {
  title: string
  /** Esc 또는 닫기 동작. 호출처가 상태를 바꿔 언마운트한다. */
  onClose: () => void
  children: ReactNode
  /** 버튼 영역(우측 정렬). */
  footer?: ReactNode
  wide?: boolean
}

/** 접근 가능한 모달 대화상자: role=dialog, aria-modal, 열 때 포커스 이동(`data-autofocus` 우선), Esc 닫기, Tab 순환, 닫을 때 포커스 복귀. */
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
    // `data-autofocus`가 있는 요소가 먼저, 없으면 첫 포커스 가능 요소(포커스만으로 목록이 열리는 콤보박스 등을 피할 때 쓴다).
    const first = dialog?.querySelector<HTMLElement>('[data-autofocus]') ?? dialog?.querySelector<HTMLElement>(FOCUSABLE)
    ;(first ?? dialog)?.focus()

    if (dialog) openDialogs.push(dialog)

    function onKeyDown(event: KeyboardEvent) {
      if (!dialog || !isTopDialog(dialog)) return
      if (event.key === 'Escape') {
        event.stopPropagation()
        onCloseRef.current()
        return
      }
      if (event.key !== 'Tab') return
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
      const index = dialog ? openDialogs.indexOf(dialog) : -1
      if (index >= 0) openDialogs.splice(index, 1)
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
