import { describe, it } from 'vitest'
import { expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

/** 서버 PL-R6·PL-R7의 403 문구 (docs/features/platform-common.md). */
const READ_ONLY_DENIED = '이 작업을 할 권한이 없습니다(읽기 전용 계정)'
const ADMIN_DENIED = '관리자 권한이 필요합니다'

describe('Fake 역할 가드의 403 문구', () => {
  // 업무 쓰기 가드: user는 읽기 전용 문구로 거절된다.
  it('user가 업무 쓰기 경로를 부르면 읽기 전용 문구의 403이다', async () => {
    // given: user(읽기 전용)로 로그인한다
    const han = await mockAs('han')
    // when·then: Action 유형 생성(업무 쓰기 가드)을 요청한다 → 403 읽기 전용 문구
    await expectApiError(han.gateway.actionTypes.create('새 유형'), 403, READ_ONLY_DENIED)
  })

  // 관리자 가드: sales도 관리자 문구로 거절된다.
  it('sales가 관리자 전용 경로를 부르면 관리자 문구의 403이다', async () => {
    // given: sales로 로그인한다
    const kim = await mockAs('kim')
    // when·then: Vendor 생성(관리자 가드)을 요청한다 → 403 관리자 문구
    await expectApiError(kim.gateway.vendors.create('새 벤더'), 403, ADMIN_DENIED)
  })

  // 관리자 가드가 쓰기 가드보다 먼저라 user도 관리자 문구를 받는다.
  it('user가 관리자 전용 경로를 부르면 읽기 전용이 아니라 관리자 문구의 403이다', async () => {
    // given: user로 로그인한다
    const han = await mockAs('han')
    // when·then: Vendor 생성을 요청한다 → 403 관리자 문구
    await expectApiError(han.gateway.vendors.create('새 벤더'), 403, ADMIN_DENIED)
  })

  // 본인 계정 삭제는 권한 문제가 아니라 상태 충돌이다(US-R16).
  it('admin이 본인 계정을 삭제하면 서버처럼 409 문구다', async () => {
    // given: admin으로 로그인한다
    const root = await mockAs('root')
    // when·then: 본인을 삭제한다 → 409
    await expectApiError(root.gateway.users.remove(USER_ID.root), 409, '자기 자신은 삭제할 수 없습니다')
  })
})
