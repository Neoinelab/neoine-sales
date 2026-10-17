/** 게이트웨이 구현이 공유하는 실행 맥락(저장소·시계·지연)과 로그인·권한 확인. */

import { canManageMasterData, canWrite, type Viewer } from '../../../shared/model/permissions'
import type { MockClock } from '../clock'
import { forbidden, unauthorized } from '../errors'
import type { Latency } from '../latency'
import type { MockStore, UserRecord } from '../store'

/** 세션 사용자 id를 보관하는 sessionStorage 키(Fake의 로그인 유지용, 읽기/쓰기는 try/catch). */
const SESSION_STORAGE_KEY = 'neoine-mock-user-id'

export interface MockContext {
  store: MockStore
  clock: MockClock
  latency: Latency
  /** 0 이상 1 미만. Deal code 추출에 쓴다. */
  random: () => number
  /** true면 로그인 사용자 id를 sessionStorage에 보관한다(개발 서버). */
  persistSession: boolean
}

/** 읽기: 지연 후 결과. */
export function read<T>(ctx: MockContext, fn: () => T): Promise<T> {
  return ctx.latency.run('read', fn)
}

/** 쓰기: 지연이 더 길다. 실패하면 아무것도 바꾸지 않아야 하므로 fn은 검증을 먼저 끝낸다. */
export function write<T>(ctx: MockContext, fn: () => T): Promise<T> {
  return ctx.latency.run('write', fn)
}

export function sessionUser(ctx: MockContext): UserRecord | null {
  const id = ctx.store.session.userId
  if (id === null) return null
  const user = ctx.store.data.users.find((u) => u.id === id)
  return user && user.status === 'active' ? user : null
}

/** 로그인 필요(401). 퇴사 처리된 세션도 로그인 전과 같다. */
export function requireUser(ctx: MockContext): UserRecord {
  const user = sessionUser(ctx)
  if (!user) throw unauthorized()
  return user
}

/** sales/admin만(user는 403). */
export function requireWrite(ctx: MockContext): UserRecord {
  const user = requireUser(ctx)
  if (!canWrite(user.role)) throw forbidden()
  return user
}

/** admin만. */
export function requireAdmin(ctx: MockContext): UserRecord {
  const user = requireUser(ctx)
  if (!canManageMasterData(user.role)) throw forbidden()
  return user
}

export function viewerOf(user: UserRecord): Viewer {
  return { id: user.id, role: user.role }
}

export function setSession(ctx: MockContext, userId: string | null): void {
  ctx.store.session.userId = userId
  if (!ctx.persistSession) return
  try {
    if (userId === null) window.sessionStorage.removeItem(SESSION_STORAGE_KEY)
    else window.sessionStorage.setItem(SESSION_STORAGE_KEY, userId)
  } catch {
    // 저장소 접근 실패(사생활 보호 모드 등)는 무시한다. 새로고침 시 로그인 화면으로 돌아갈 뿐이다.
  }
}

export function readStoredSession(): string | null {
  try {
    return window.sessionStorage.getItem(SESSION_STORAGE_KEY)
  } catch {
    return null
  }
}

/** 순수 JSON 데이터의 깊은 복사(반환 객체를 바꿔도 저장소에 영향이 없도록). */
export function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}
