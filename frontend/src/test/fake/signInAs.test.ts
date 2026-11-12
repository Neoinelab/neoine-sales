import { describe, expect, it } from 'vitest'
import { expectApiError, mockAs } from './testing'
import { NO_SUCH_ID, USER_ID } from './seed/ids'

/** Fake 전용 테스트 로그인 도우미 `MockInstance.signInAs`의 계약(운영 게이트웨이에는 없다). */
describe('MockInstance.signInAs', () => {
  it('재직 중인 시드 사용자로 로그인하고 마지막 로그인 시각을 갱신한다', async () => {
    // given: 로그인하지 않은 Fake와 고정한 시계
    const mock = await mockAs(null)
    mock.clock.setNow('2026-10-15T09:00:00+09:00')

    // when: 김영업으로 로그인한 뒤 내 정보를 읽고, 다른 사용자(root)로 바꿔 목록을 읽는다
    const me = await mock.signInAs(USER_ID.kim)
    const current = await mock.gateway.auth.me()
    await mock.signInAs(USER_ID.root)
    const kim = (await mock.gateway.users.list('all')).find((u) => u.id === USER_ID.kim)

    // then: 현재 사용자가 김영업이고 마지막 로그인 시각이 시계의 지금이다
    expect(me).toMatchObject({ id: USER_ID.kim, role: 'sales' })
    expect(current).toEqual(me)
    expect(kim?.lastLoginAt).toBe(mock.clock.now())
  })

  it('퇴사한 사용자는 401로 거절하고 로그아웃 상태를 유지한다', async () => {
    // given: 로그인하지 않은 Fake
    const mock = await mockAs(null)

    // when·then: 퇴사 사용자로 로그인하면 401이고, 이어서 내 정보도 401이다
    await expectApiError(mock.signInAs(USER_ID.old), 401, '아이디 또는 비밀번호가 올바르지 않습니다')

    await expectApiError(mock.gateway.auth.me(), 401)
  })

  it('모르는 id는 401로 거절한다', async () => {
    // given: 로그인하지 않은 Fake
    const mock = await mockAs(null)

    // when·then: 없는 id로 로그인하면 401이다
    await expectApiError(mock.signInAs(NO_SUCH_ID), 401)
  })

  it('세션을 다른 사용자로 바꾼다', async () => {
    // given: root로 로그인한 Fake
    const mock = await mockAs('root')

    // when: 다른 사용자로 로그인한다
    await mock.signInAs(USER_ID.han)

    // then: 현재 사용자가 그 사용자이다
    expect(await mock.gateway.auth.me()).toMatchObject({ id: USER_ID.han, role: 'user' })
  })
})
