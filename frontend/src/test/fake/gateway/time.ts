import type { TimeGateway } from '../../../gateway/types'
import { read, requireUser, type MockContext } from './context'

/**
 * 서버 시각(`GET /api/v1/time`)의 Fake. 로그인 사용자만(401). Fake 시계가 곧 서버 시계라서
 * `now`는 시계의 지금(오프셋 포함 ISO), `today`는 그 달력 날짜다.
 */
export function createTimeGateway(ctx: MockContext): TimeGateway {
  return {
    get: () =>
      read(ctx, () => {
        requireUser(ctx)
        return { now: ctx.clock.now(), today: ctx.clock.today() }
      }),
  }
}
