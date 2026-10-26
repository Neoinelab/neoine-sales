/**
 * 앱이 쓰는 게이트웨이와 시계. 화면은 `data/*` 훅만 쓰고, 훅은 여기서 내보내는 `gateway`·`clock`만 안다.
 * 앱에는 실제 서버(`gateway/http`) 구현만 있다. 테스트는 `test/setup.ts`가 이 모듈을 Fake(`test/fake`)로 바꿔 끼운다.
 */

import { createServerClock } from './clock'
import { createHttpGateway } from './http'
import type { Clock, Gateway } from './types'

export type { Gateway, Clock } from './types'

export const gateway: Gateway = createHttpGateway()
export const clock: Clock = createServerClock()
