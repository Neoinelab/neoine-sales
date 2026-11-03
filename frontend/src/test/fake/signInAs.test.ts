import { describe, expect, it } from 'vitest'
import { expectApiError, mockAs } from './testing'
import { NO_SUCH_ID, USER_ID } from './seed/ids'

/** Fake 전용 테스트 로그인 도우미 `MockInstance.signInAs`의 계약(운영 게이트웨이에는 없다). */
describe('MockInstance.signInAs', () => {
  it('signs in an active seed user and updates lastLoginAt', async () => {
    const mock = await mockAs(null)
    mock.clock.setNow('2026-10-15T09:00:00+09:00')

    const me = await mock.signInAs(USER_ID.kim)

    expect(me).toMatchObject({ id: USER_ID.kim, role: 'sales' })
    expect(await mock.gateway.auth.me()).toEqual(me)
    await mock.signInAs(USER_ID.root)
    const kim = (await mock.gateway.users.list('all')).find((u) => u.id === USER_ID.kim)
    expect(kim?.lastLoginAt).toBe(mock.clock.now())
  })

  it('rejects a resigned user with 403 and stays signed out', async () => {
    const mock = await mockAs(null)

    await expectApiError(mock.signInAs(USER_ID.old), 403, '퇴사한 사용자는 로그인할 수 없습니다.')

    await expectApiError(mock.gateway.auth.me(), 401)
  })

  it('rejects an unknown id with 401', async () => {
    const mock = await mockAs(null)

    await expectApiError(mock.signInAs(NO_SUCH_ID), 401)
  })

  it('switches the session to another user', async () => {
    const mock = await mockAs('root')

    await mock.signInAs(USER_ID.han)

    expect(await mock.gateway.auth.me()).toMatchObject({ id: USER_ID.han, role: 'user' })
  })
})
