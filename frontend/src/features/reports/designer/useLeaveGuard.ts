import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'

/**
 * 작성 중인 화면을 떠나기 전 확인(`active`일 때만).
 * react-router의 `useBlocker`는 데이터 라우터(createBrowserRouter)에서만 쓸 수 있고 이 앱은 선언형 `BrowserRouter`라서,
 * (1) 새로고침·탭 닫기는 `beforeunload`로, (2) 앱 안 링크 클릭은 문서 capture 단계에서 가로채 확인 대화상자로 묻는다.
 * 브라우저 뒤로 가기와 `navigate()` 직접 호출 이동은 막지 않는다(사용자 결정 Q2=A).
 */
export function useLeaveGuard(active: boolean): { pending: string | null; confirm: () => void; cancel: () => void } {
  const navigate = useNavigate()
  const location = useLocation()
  const [pending, setPending] = useState<string | null>(null)
  const anchorRef = useRef<HTMLAnchorElement | null>(null)
  const replaying = useRef(false)

  useEffect(() => {
    if (!active) return
    const onUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    const onClick = (event: MouseEvent) => {
      if (replaying.current || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
      const target = event.target instanceof Element ? event.target : null
      const anchor = target?.closest('a[href]')
      if (!(anchor instanceof HTMLAnchorElement)) return
      const targetWindow = anchor.getAttribute('target')
      if ((targetWindow && targetWindow !== '_self') || anchor.hasAttribute('download')) return
      const url = new URL(anchor.href, window.location.href)
      if (url.origin !== window.location.origin || url.pathname === location.pathname) return
      event.preventDefault()
      event.stopPropagation()
      anchorRef.current = anchor
      setPending(url.pathname + url.search + url.hash)
    }
    window.addEventListener('beforeunload', onUnload)
    document.addEventListener('click', onClick, true)
    return () => {
      window.removeEventListener('beforeunload', onUnload)
      document.removeEventListener('click', onClick, true)
    }
  }, [active, location.pathname])

  const confirm = useCallback(() => {
    if (pending === null) return
    setPending(null)
    const anchor = anchorRef.current
    anchorRef.current = null
    if (anchor?.isConnected) {
      // 가로챈 클릭을 그대로 다시 보내 링크의 원래 동작(이동, 좁은 화면 메뉴 닫기 등)을 살린다.
      replaying.current = true
      try {
        anchor.click()
      } finally {
        replaying.current = false
      }
      return
    }
    void navigate(pending)
  }, [navigate, pending])
  const cancel = useCallback(() => setPending(null), [])
  return { pending, confirm, cancel }
}
