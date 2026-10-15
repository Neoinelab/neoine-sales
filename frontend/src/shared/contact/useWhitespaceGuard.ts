import { useCallback, useEffect, useRef, useState } from 'react'
import { stripWhitespace } from '../model/contactRules'

const FLASH_MS = 3000

/**
 * 입력 중 공백을 제거하고, 제거가 일어난 필드를 잠깐(3초, 이후 입력과 무관하게 자동 해제) 표시하게 한다. 붙여넣기도 같은 경로다.
 * `guard(field, raw)`는 공백을 뺀 문자열을 돌려준다. `flashed[field]`가 true인 동안 안내 문구를 보인다.
 */
export function useWhitespaceGuard() {
  const [flashed, setFlashed] = useState<Record<string, boolean>>({})
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})

  useEffect(() => {
    const current = timers.current
    return () => Object.values(current).forEach(clearTimeout)
  }, [])

  const guard = useCallback((field: string, raw: string): string => {
    const stripped = stripWhitespace(raw)
    if (stripped !== raw) {
      const timer = timers.current[field]
      if (timer) clearTimeout(timer)
      setFlashed((f) => ({ ...f, [field]: true }))
      timers.current[field] = setTimeout(() => setFlashed((f) => ({ ...f, [field]: false })), FLASH_MS)
    }
    return stripped
  }, [])

  return { flashed, guard }
}
