/** 테스트가 쓰는 기본 Fake 인스턴스. `test/setup.ts`가 앱의 `gateway/index.ts`를 이 인스턴스로 바꿔 끼운다(앱 번들에는 들어가지 않는다). */

import { createMockGateway } from './index'
import type { MockControl } from './types'

export const defaultMock = createMockGateway({ persistSession: true })
export const mockControl: MockControl = defaultMock.control

export interface ResetMockOptions {
  /** 문자열이면 그 시각으로 고정, null이면 실제 시각으로 복귀, 생략하면 그대로. */
  now?: string | null
  /** 문자열이면 그 사용자로 로그인, null이면 로그아웃, 생략하면 현재 로그인 유지. */
  userId?: string | null
}

/**
 * 기본 인스턴스를 현재 시드로 되돌린다(기본은 업무 데이터 없는 시드, 테스트는 `test/setup.ts`가 샘플 픽스처 시드로 바꿔 둔다).
 * 테스트의 `beforeEach`가 쓴다.
 * 저장소 장애 시뮬레이션은 꺼진다. 쿼리 캐시 무효화는 호출자가 한다.
 */
export function resetMock(options: ResetMockOptions = {}): void {
  if (options.now !== undefined) defaultMock.clock.setNow(options.now)
  defaultMock.control.resetData()
  if (options.userId !== undefined) defaultMock.setSession(options.userId)
}
