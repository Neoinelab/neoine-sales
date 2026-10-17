import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'
import { defaultMock } from './fake/default'
import { buildSampleSeed } from './fixtures/sampleSeed'

// 앱의 gateway 모듈(실제 서버 http 게이트웨이)을 모든 테스트에서 Fake로 바꿔 끼운다. 앱 코드에는 분기가 없다.
// http 게이트웨이 테스트는 `gateway/http`를 직접 import하므로 영향이 없고, 원본이 필요하면 `vi.importActual`을 쓴다.
vi.mock('../gateway', async () => {
  const fake = await import('./fake/default')
  return { gateway: fake.defaultMock.gateway, clock: fake.defaultMock.clock }
})

// 앱 기본 시드는 업무 데이터가 없다. 테스트는 매번 샘플 픽스처 시드로 시작한다(빈 상태 테스트는 renderAt의 seed: 'empty').
beforeEach(() => {
  defaultMock.setSeed(buildSampleSeed)
})

afterEach(() => {
  cleanup()
  // 로그인 사용자 id를 보관하는 Fake 세션이 테스트 사이에 새지 않게 한다.
  try {
    window.sessionStorage.clear()
  } catch {
    // 저장소를 쓸 수 없는 환경이면 그대로 둔다.
  }
})
