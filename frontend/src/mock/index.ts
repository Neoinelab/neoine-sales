/**
 * mock 게이트웨이 조립. 사용법
 *
 *   const mock = createMockGateway({ now: '2026-10-15T09:00:00+09:00', latency: false })
 *   await mock.gateway.auth.quickLogin('u-kim')
 *   mock.control.resetData()      // 시드 복원(로그인 유지)
 *   mock.clock.advance(60_000)    // 고정 시계를 1분 앞으로
 *
 * 앱은 `gateway/index.ts`가 내보내는 기본 인스턴스(`mock/default.ts`)를 쓰고, 테스트는 `resetMock()`으로 그 인스턴스를 초기화한다.
 */

import type { Gateway, MockControl } from '../gateway/types'
import { createClock, type MockClock } from './clock'
import { createMockControl } from './control'
import { readStoredSession, setSession, type MockContext } from './gateway/context'
import { createGatewayFor } from './gateway'
import { createLatency } from './latency'
import { buildSeed, type SeedFactory } from './seed'
import { createStore } from './store'

export type { SeedFactory } from './seed'
export { seedDealCode } from './seed'

export interface MockOptions {
  /** 고정 시각(오프셋 포함 ISO). 생략하면 실제 시각. */
  now?: string | null
  /** false면 지연 없음. 생략하면 개발 서버에서만 지연(테스트 모드는 0ms). */
  latency?: boolean
  /** true면 로그인 사용자 id를 sessionStorage에 보관/복원한다(앱 기본 인스턴스). */
  persistSession?: boolean
  /** 시드 교체(테스트용). 기본은 계획 4.3의 시드. */
  seed?: SeedFactory
  /** Deal code 추출용 난수(0 이상 1 미만). */
  random?: () => number
  /** 처음부터 로그인해 둘 사용자 id. */
  userId?: string | null
}

export interface MockInstance {
  gateway: Gateway
  control: MockControl
  clock: MockClock
  /** 로그인 상태를 직접 지정한다(null=로그아웃). 존재하지 않거나 퇴사한 id는 로그아웃으로 처리한다. */
  setSession(userId: string | null): void
}

export function createMockGateway(options: MockOptions = {}): MockInstance {
  const clock = createClock(options.now ?? null)
  const seed = options.seed ?? buildSeed
  const persistSession = options.persistSession ?? false
  const latencyAvailable = options.latency ?? import.meta.env.MODE !== 'test'
  const initialUser = options.userId ?? (persistSession ? readStoredSession() : null)
  const ctx: MockContext = {
    store: createStore(seed(clock), null),
    clock,
    latency: createLatency(latencyAvailable),
    random: options.random ?? Math.random,
    persistSession,
  }
  const signIn = (userId: string | null): void => {
    const user = ctx.store.data.users.find((u) => u.id === userId)
    setSession(ctx, user && user.status === 'active' ? user.id : null)
  }
  signIn(initialUser)

  const reseed = (): void => {
    const keep = ctx.store.session.userId
    ctx.store.data = seed(clock)
    ctx.store.storageFailure = false
    signIn(keep)
  }
  return {
    gateway: createGatewayFor(ctx),
    control: createMockControl(ctx, reseed),
    clock,
    setSession: signIn,
  }
}
