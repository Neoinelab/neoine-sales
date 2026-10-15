import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'
import { defaultMock } from '../mock/default'
import { buildSampleSeed } from './fixtures/sampleSeed'

// 앱 기본 시드는 업무 데이터가 없다. 테스트는 매번 샘플 픽스처 시드로 시작한다(빈 상태 테스트는 renderAt의 seed: 'empty').
beforeEach(() => {
  defaultMock.setSeed(buildSampleSeed)
})

afterEach(() => {
  cleanup()
  // 로그인 사용자 id를 보관하는 mock 세션이 테스트 사이에 새지 않게 한다.
  try {
    window.sessionStorage.clear()
  } catch {
    // 저장소를 쓸 수 없는 환경이면 그대로 둔다.
  }
})
