/**
 * mock 게이트웨이 조립. 사용법
 *
 *   const mock = createMockGateway({ now: '2026-10-15T09:00:00+09:00', latency: false })
 *   await mock.gateway.auth.quickLogin(USER_ID.kim)
 *   mock.control.resetData()      // 시드 복원(로그인 유지)
 *   mock.clock.advance(60_000)    // 고정 시계를 1분 앞으로
 *
 * 테스트는 `test/setup.ts`가 `gateway/index.ts` 자리에 끼워 넣는 기본 인스턴스(`default.ts`)를 쓰고, `resetMock()`으로 초기화한다.
 */

import type { Gateway } from '../../gateway/types'
import { createClock, type MockClock } from './clock'
import { createMockControl } from './control'
import type { MockControl } from './types'
import { readStoredSession, setSession, type MockContext } from './gateway/context'
import { createGatewayFor } from './gateway'
import { createLatency } from './latency'
import { emptyBusinessSeed, type SeedFactory } from './seed'
import { createStore, emptyReportsState } from './store'

export type { SeedFactory } from './seed'

export interface MockOptions {
  /** 고정 시각(오프셋 포함 ISO). 생략하면 실제 시각. */
  now?: string | null
  /** false면 지연 없음. 생략하면 개발 서버에서만 지연(테스트 모드는 0ms). */
  latency?: boolean
  /** true면 로그인 사용자 id를 sessionStorage에 보관/복원한다(앱 기본 인스턴스). */
  persistSession?: boolean
  /** 시드 교체(테스트용). 기본은 업무 데이터가 없는 `emptyBusinessSeed`. 샘플 업무 데이터는 테스트 픽스처(`test/fixtures`)가 공급한다. */
  seed?: SeedFactory
  /** Deal code 추출용 난수(0 이상 1 미만). */
  random?: () => number
  /** 처음부터 로그인해 둘 사용자 id. */
  userId?: number | null
}

export interface MockInstance {
  gateway: Gateway
  control: MockControl
  clock: MockClock
  /** 로그인 상태를 직접 지정한다(null=로그아웃). 존재하지 않거나 퇴사한 id는 로그아웃으로 처리한다. */
  setSession(userId: number | null): void
  /** 시드를 교체하고 즉시 그 시드로 되돌린다(`control.resetData()`도 이후 이 시드를 쓴다). 테스트 전용. */
  setSeed(factory: SeedFactory): void
}

export function createMockGateway(options: MockOptions = {}): MockInstance {
  const clock = createClock(options.now ?? null)
  let seed: SeedFactory = options.seed ?? emptyBusinessSeed
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
  const signIn = (userId: number | null): void => {
    const user = ctx.store.data.users.find((u) => u.id === userId)
    setSession(ctx, user && user.status === 'active' ? user.id : null)
  }
  signIn(initialUser)

  const reseed = (): void => {
    const keep = ctx.store.session.userId
    ctx.store.data = seed(clock)
    ctx.store.storageFailure = false
    ctx.store.reports = emptyReportsState()
    signIn(keep)
  }
  return {
    gateway: createGatewayFor(ctx),
    control: createMockControl(ctx, reseed),
    clock,
    setSession: signIn,
    setSeed(factory) {
      seed = factory
      reseed()
    },
  }
}
