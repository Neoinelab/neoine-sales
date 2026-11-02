import { describe, expect, it } from 'vitest'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'
import { SEED_PASSWORD } from '../seed/users'
import { expectApiError, mockAs } from '../testing'

/** 서버 `POST /users`·`PATCH /users/{id}`·`PUT /users/{id}/password`와 같은 문구·판정 순서 (계획 AC-6~8). */
const AD_MANAGED = 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다'
const LOCAL_ONLY = '앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.'
const RESIGNED = '이미 퇴사 처리된 사용자입니다.'
const WEAK = '비밀번호는 8자 이상이어야 합니다.'
const PW = 'Passw0rd-ok'
const NEW_PW = 'Fresh-passw0rd'

async function localAdmin() {
  const mock = await mockAs('root')
  mock.control.setAuthMode('local')
  return mock
}

const NEW_USER = { loginId: 'newbie', name: '신입영업', role: 'sales' as const, password: PW, email: 'newbie@corp.test', phone: '010-1234-5678' }

describe('users.list phone (AC-6)', () => {
  it('carries a null phone for users who have none', async () => {
    const { gateway } = await mockAs('root')

    const users = await gateway.users.list('all')

    expect(users.every((u) => u.phone === null)).toBe(true)
  })
})

describe('users.create in local mode (AC-6)', () => {
  it('registers the user with profile and password, who can then sign in', async () => {
    const { gateway } = await localAdmin()

    const created = await gateway.users.create(NEW_USER)

    expect(created).toMatchObject({ loginId: 'newbie', name: '신입영업', email: 'newbie@corp.test', phone: '010-1234-5678', status: 'active' })
    expect(JSON.stringify(created)).not.toContain(PW)
    await gateway.auth.logout()
    expect((await gateway.auth.login('newbie', PW)).me).toMatchObject({ loginId: 'newbie', role: 'sales' })
    await expectApiError(gateway.auth.login('newbie', 'wrong-password'), 401)
  })

  it('treats a missing email and phone as null', async () => {
    const { gateway } = await localAdmin()

    const created = await gateway.users.create({ loginId: 'newbie', name: '신입영업', role: 'user', password: PW })

    expect(created).toMatchObject({ email: null, phone: null })
  })

  it.each([
    ['without a password', { password: undefined }, '비밀번호를 입력하세요.'],
    ['with a weak password', { password: 'short7!' }, WEAK],
    ['with the id as the password', { loginId: 'newbie.id', password: 'Newbie.Id' }, '비밀번호는 아이디와 같을 수 없습니다.'],
    ['without a name', { name: ' ' }, '이름을 입력하세요.'],
    ['with an invalid email', { email: 'not-an-email' }, '이메일 형식이 올바르지 않습니다.'],
    ['with an invalid phone', { phone: '12' }, '전화번호 형식이 올바르지 않습니다.'],
  ])('rejects a registration %s with 422', async (_name, override, message) => {
    const { gateway } = await localAdmin()

    await expectApiError(gateway.users.create({ ...NEW_USER, ...override }), 422, message)

    expect((await gateway.users.list('all')).some((u) => u.loginId.startsWith('newbie'))).toBe(false)
  })

  it('rejects an id already in use with 409', async () => {
    const { gateway } = await localAdmin()

    await expectApiError(gateway.users.create({ ...NEW_USER, loginId: 'kim' }), 409, '이미 사용 중인 아이디입니다.')
  })

  it('rejects the reserved dev ids with 422', async () => {
    const { gateway } = await localAdmin()

    await expectApiError(gateway.users.create({ ...NEW_USER, loginId: 'dev-admin' }), 422, /개발 로그인 전용 아이디/)
  })
})

describe('users.create in AD mode (AC-6)', () => {
  it('rejects a password with 422', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.users.create(NEW_USER), 422)
  })

  it('accepts phone and email without a password', async () => {
    const { gateway } = await mockAs('root')

    const created = await gateway.users.create({ loginId: 'newbie', name: '신입영업', role: 'sales', phone: '010-1234-5678', email: 'n@corp.test' })

    expect(created).toMatchObject({ phone: '010-1234-5678', email: 'n@corp.test' })
  })
})

describe('users.update (AC-8)', () => {
  it('changes name, email and phone in local mode and returns the user', async () => {
    const { gateway } = await localAdmin()

    const changed = await gateway.users.update(USER_ID.kim, { name: '김새이름', email: 'New@Corp.test', phone: '02-123-4567' })

    expect(changed).toMatchObject({ id: USER_ID.kim, loginId: 'kim', name: '김새이름', email: 'new@corp.test', phone: '02-123-4567', role: 'sales' })
    expect((await gateway.users.list('all')).find((u) => u.id === USER_ID.kim)).toEqual(changed)
  })

  it('keeps omitted fields and clears a field given as null', async () => {
    const { gateway } = await localAdmin()
    await gateway.users.update(USER_ID.kim, { phone: '02-123-4567' })

    const changed = await gateway.users.update(USER_ID.kim, { phone: null })

    expect(changed).toMatchObject({ name: '김영업', email: 'kim@neoine.test', phone: null })
  })

  it.each([
    ['a blank name', { name: '' }, /이름/],
    ['an invalid email', { email: 'abc' }, '이메일 형식이 올바르지 않습니다.'],
    ['an invalid phone', { phone: '12' }, '전화번호 형식이 올바르지 않습니다.'],
  ])('rejects %s with 422 and changes nothing', async (_name, input, message) => {
    const { gateway } = await localAdmin()

    await expectApiError(gateway.users.update(USER_ID.kim, input), 422, message)

    expect((await gateway.users.list('all')).find((u) => u.id === USER_ID.kim)).toMatchObject({ name: '김영업', email: 'kim@neoine.test' })
  })

  it.each([{ name: '새 이름' }, { email: 'a@b.co' }])('refuses %j in AD mode with 409', async (input) => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.users.update(USER_ID.kim, input), 409, AD_MANAGED)
  })

  it('lets the phone be changed in AD mode', async () => {
    const { gateway } = await mockAs('root')

    const changed = await gateway.users.update(USER_ID.kim, { phone: '02-123-4567' })

    expect(changed.phone).toBe('02-123-4567')
  })

  it('refuses a resigned user with 409 and an unknown user with 404', async () => {
    const { gateway } = await localAdmin()

    await expectApiError(gateway.users.update(USER_ID.old, { phone: '02-123-4567' }), 409, RESIGNED)
    await expectApiError(gateway.users.update(NO_SUCH_ID, { phone: '02-123-4567' }), 404)
  })

  it.each(['kim', 'han'] as const)('is admin only: %s gets 403', async (key) => {
    const { gateway } = await mockAs(key)

    await expectApiError(gateway.users.update(USER_ID.park, { phone: '02-123-4567' }), 403)
  })
})

describe('users.resetPassword (AC-7)', () => {
  it('sets the new password: the user signs in with it and no longer with the old one', async () => {
    const { gateway } = await localAdmin()

    await expect(gateway.users.resetPassword(USER_ID.kim, NEW_PW)).resolves.toBeUndefined()

    await gateway.auth.logout()
    await expectApiError(gateway.auth.login('kim', SEED_PASSWORD), 401)
    expect((await gateway.auth.login('kim', NEW_PW)).me).toMatchObject({ loginId: 'kim' })
  })

  it('refuses in AD mode with 409', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.users.resetPassword(USER_ID.kim, NEW_PW), 409, LOCAL_ONLY)
  })

  it('refuses the admin own password with 409', async () => {
    const { gateway } = await localAdmin()

    await expectApiError(gateway.users.resetPassword(USER_ID.root, NEW_PW), 409)
  })

  it('refuses a resigned user with 409 and an unknown user with 404', async () => {
    const { gateway } = await localAdmin()

    await expectApiError(gateway.users.resetPassword(USER_ID.old, NEW_PW), 409, RESIGNED)
    await expectApiError(gateway.users.resetPassword(NO_SUCH_ID, NEW_PW), 404)
  })

  it('refuses a weak password with 422 and keeps the old one', async () => {
    const { gateway } = await localAdmin()

    await expectApiError(gateway.users.resetPassword(USER_ID.kim, 'short7!'), 422, WEAK)

    await gateway.auth.logout()
    expect((await gateway.auth.login('kim', SEED_PASSWORD)).me).toMatchObject({ loginId: 'kim' })
  })

  it('is admin only: sales gets 403', async () => {
    const { gateway, control } = await mockAs('kim')
    control.setAuthMode('local')

    await expectApiError(gateway.users.resetPassword(USER_ID.park, NEW_PW), 403)
  })
})
