/**
 * 앱이 쓰는 게이트웨이. 화면은 `data/*` 훅만 쓰고, 훅은 여기서 내보내는 `gateway`만 안다.
 *
 * `VITE_GATEWAY=http`(`pnpm dev:http`)면 실제 서버(`gateway/http`), 그 밖에는 메모리 mock(기본)이다. 한 실행에는 한 구현만 쓴다.
 * (mock 모듈은 번들에 들어 있지만 http 모드에서는 게이트웨이로 쓰이지 않는다. 기본값을 http로 바꾸고 mock을 test/fake로 옮기는 것은 P8.)
 * mockControl은 MockBanner·MockPanel(mock 모드에서만 그려진다)과 테스트가 쓴다.
 */

import { defaultMock, resetMock } from '../mock/default'
import { createHttpGateway } from './http'
import { gatewayMode } from './mode'
import type { Gateway, MockControl } from './types'

export type { Gateway, MockControl } from './types'

export const gateway: Gateway = gatewayMode() === 'http' ? createHttpGateway() : defaultMock.gateway
export const mockControl: MockControl = defaultMock.control

/** 테스트용: 기본 mock 인스턴스를 시드로 되돌리고 시각·로그인을 지정한다(`mock/default.ts`). */
export { resetMock }
