import { useCallback, useEffect, useRef, useState } from 'react'
import { NavigationType, useBlocker, useLocation, useNavigate } from 'react-router'

/**
 * 작성 중인 화면을 떠나기 전 확인(`active`일 때만).
 * (1) 새로고침·탭 닫기는 `beforeunload`로, (2) 앱 안 링크 클릭은 문서 capture 단계에서 가로채 확인 대화상자로,
 * (3) 브라우저 뒤로·앞으로 가기(POP)는 데이터 라우터의 `useBlocker`로 막고 같은 확인 창을 띄운다(경로가 바뀔 때만).
 * `navigate()` 직접 호출 이동은 막지 않는다. 확인 창은 한 번에 하나이며, 링크 "떠나기"는 PUSH 이동이라 blocker가 다시 막지 않는다.
 */
export function useLeaveGuard(active: boolean): { pending: string | null; confirm: () => void; cancel: () => void } {
  const navigate = useNavigate()
  const location = useLocation()
  const [pending, setPending] = useState<string | null>(null)
  const anchorRef = useRef<HTMLAnchorElement | null>(null)
  const replaying = useRef(false)
  const blocker = useBlocker(
    ({ currentLocation, nextLocation, historyAction }) =>
      active && historyAction === NavigationType.Pop && currentLocation.pathname !== nextLocation.pathname,
  )

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
    if (pending === null) {
      if (blocker.state === 'blocked') blocker.proceed()
      return
    }
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
  }, [blocker, navigate, pending])
  const cancel = useCallback(() => {
    setPending(null)
    if (blocker.state === 'blocked') blocker.reset()
  }, [blocker])
  const blockedTo = blocker.state === 'blocked' ? blocker.location.pathname + blocker.location.search + blocker.location.hash : null
  return { pending: pending ?? blockedTo, confirm, cancel }
}
