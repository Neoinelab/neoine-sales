/**
 * 앱이 쓰는 게이트웨이. 화면은 `data/*` 훅만 쓰고, 훅은 여기서 내보내는 `gateway`만 안다.
 *
 * 실제 연동으로 바꾸는 방법: 이 파일의 두 export를 HTTP 구현(`createHttpGateway()`)으로 교체한다.
 * mockControl과 `src/mock/**`는 MockBanner·MockPanel과 함께 삭제한다.
 */

import { defaultMock, resetMock } from '../mock/default'
import type { Gateway, MockControl } from './types'

export type { Gateway, MockControl } from './types'

export const gateway: Gateway = defaultMock.gateway
export const mockControl: MockControl = defaultMock.control

/** 테스트용: 기본 mock 인스턴스를 시드로 되돌리고 시각·로그인을 지정한다(`mock/default.ts`). */
export { resetMock }
