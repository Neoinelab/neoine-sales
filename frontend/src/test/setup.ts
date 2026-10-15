import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
  // 로그인 사용자 id를 보관하는 mock 세션이 테스트 사이에 새지 않게 한다.
  try {
    window.sessionStorage.clear()
  } catch {
    // 저장소를 쓸 수 없는 환경이면 그대로 둔다.
  }
})
