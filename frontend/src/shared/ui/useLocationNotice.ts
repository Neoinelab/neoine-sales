import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'

/** `navigate(to, { state: { notice } })`로 넘어온 알림 문구. 없거나 문자열이 아니면 null. */
function noticeOf(state: unknown): string | null {
  if (typeof state !== 'object' || state === null || !('notice' in state)) return null
  const notice = (state as { notice?: unknown }).notice
  return typeof notice === 'string' && notice !== '' ? notice : null
}

/**
 * 다른 화면이 넘긴 저장 알림을 읽어 한 번만 보여 준다.
 * 읽은 즉시 history state를 비워(replace) 새로고침·뒤로 가기에서 다시 나오지 않는다.
 * 반환값은 `useState`와 같은 [알림, 설정 함수]라 화면 안의 다른 알림과 같은 자리에 쓸 수 있다.
 */
export function useLocationNotice(): [string | null, (notice: string | null) => void] {
  const { state, pathname, search } = useLocation()
  const navigate = useNavigate()
  const incoming = noticeOf(state)
  const [seen, setSeen] = useState<string | null>(incoming)
  const [notice, setNotice] = useState<string | null>(incoming)

  if (incoming !== seen) {
    // 렌더 중 상태 조정: 같은 화면에 새 알림이 도착한 경우(같은 문구의 재도착 포함, 비워지면 seen도 비운다).
    setSeen(incoming)
    if (incoming !== null) setNotice(incoming)
  }

  useEffect(() => {
    if (incoming !== null) void navigate({ pathname, search }, { replace: true, state: null })
  }, [incoming, pathname, search, navigate])

  return [notice, setNotice]
}
