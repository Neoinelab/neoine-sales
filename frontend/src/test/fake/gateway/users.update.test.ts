import { describe, it } from 'vitest'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'
import { expectApiError, mockAs } from '../testing'

/** 서버 `PATCH /users/{id}` 판정 순서(US-R14): AD 이름·이메일 409 → 404 → 퇴사 409 → 값 검증 422. */
const AD_MANAGED = 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다.'
const RESIGNED = '이미 퇴사 처리된 사용자입니다'

describe('users.update decision order', () => {
  // AD 모드에서 이름을 보내면 없는 사용자여도 AD 409가 먼저다
  it('answers the AD 409 before the 404 for an unknown user', async () => {
    // given: AD 모드의 admin이다
    const { gateway } = await mockAs('root')

    // when·then: 없는 id의 이름을 고친다 → 404가 아니라 AD 관리 409다
    await expectApiError(gateway.users.update(NO_SUCH_ID, { name: '새 이름' }), 409, AD_MANAGED)
  })

  // AD 모드에서 이메일을 보내면 퇴사자여도 AD 409가 먼저다
  it('answers the AD 409 before the resigned 409 for a resigned user', async () => {
    // given: AD 모드의 admin이다
    const { gateway } = await mockAs('root')

    // when·then: 퇴사자의 이메일을 고친다 → 퇴사 문구가 아니라 AD 관리 409다
    await expectApiError(gateway.users.update(USER_ID.old, { email: 'a@corp.test' }), 409, AD_MANAGED)
  })

  // AD 모드에서 전화만 보내면 AD 규칙에 걸리지 않고 404·퇴사 판정으로 간다
  it('lets a phone-only change reach the 404 and resigned checks in AD mode', async () => {
    // given: AD 모드의 admin이다
    const { gateway } = await mockAs('root')

    // when·then: 없는 id와 퇴사자의 전화를 고친다 → 각각 404와 퇴사 409다
    await expectApiError(gateway.users.update(NO_SUCH_ID, { phone: '02-123-4567' }), 404)
    await expectApiError(gateway.users.update(USER_ID.old, { phone: '02-123-4567' }), 409, RESIGNED)
  })
})
