import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import type { Me } from '../model/types'

interface Props {
  me: Me
  /** 메뉴 항목을 골라 메뉴가 닫힌 뒤(모바일 상단 메뉴를 함께 접는 데 쓴다). */
  onPicked?: () => void
  onLogout: () => void
}

/** 상단 바 오른쪽 사용자 아이콘 메뉴: 이름(역할), 내 정보, 로그아웃. Esc·바깥 클릭·아이콘 재클릭으로 닫힌다. */
export function UserMenu({ me, onPicked, onLogout }: Props) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    rootRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus()
    function onPointerDown(event: MouseEvent) {
      if (event.target instanceof Node && !rootRef.current?.contains(event.target)) setOpen(false)
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      setOpen(false)
      triggerRef.current?.focus()
    }
    document.addEventListener('mousedown', onPointerDown)
    document.addEventListener('keydown', onKeyDown)
    return () => {
      document.removeEventListener('mousedown', onPointerDown)
      document.removeEventListener('keydown', onKeyDown)
    }
  }, [open])

  function pick(action?: () => void) {
    setOpen(false)
    onPicked?.()
    action?.()
  }

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        ref={triggerRef}
        className="user-menu-trigger"
        aria-label="사용자 메뉴"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <circle cx="12" cy="8" r="4" />
          <path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8" />
        </svg>
      </button>
      {open && (
        <div className="user-menu-panel" role="menu" aria-label="사용자">
          <p className="user-menu-name">
            {me.name} ({me.role})
          </p>
          <Link role="menuitem" to="/me" onClick={() => pick()}>
            내 정보
          </Link>
          <button type="button" role="menuitem" onClick={() => pick(onLogout)}>
            로그아웃
          </button>
        </div>
      )}
    </div>
  )
}
