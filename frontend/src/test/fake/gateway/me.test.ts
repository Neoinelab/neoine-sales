import { describe, expect, it } from 'vitest'
import { SEED_PASSWORD } from '../seed/users'
import { expectApiError, mockAs } from '../testing'

/** 서버 `GET·PATCH /me/profile`·`PUT /me/password`와 같은 문구·판정 순서 (계획 AC-9~11). */
const AD_MANAGED = 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다'
const LOCAL_ONLY = '앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.'
const WRONG_CURRENT = '현재 비밀번호가 올바르지 않습니다.'
const WEAK = '비밀번호는 8자 이상이어야 합니다.'
const NEW_PW = 'Fresh-passw0rd'

async function localAs(key: 'root' | 'kim' | 'han') {
  const mock = await mockAs(key)
  mock.control.setAuthMode('local')
  return mock
}

describe('me.profile (AC-9)', () => {
  it.each([
    ['root', 'admin'],
    ['kim', 'sales'],
    ['han', 'user'],
  ] as const)('shows the %s profile with every field editable in local mode', async (key, role) => {
    const { gateway } = await localAs(key)

    const profile = await gateway.me.profile()

    expect(profile).toMatchObject({ loginId: key, role, authMode: 'local', phone: null })
    expect(profile.email).toBe(`${key}@neoine.test`)
    expect(profile.editable).toEqual({ name: true, email: true, phone: true, password: true })
  })

  it('allows only the phone in AD mode and no password change', async () => {
    const { gateway } = await mockAs('kim')

    const profile = await gateway.me.profile()

    expect(profile.authMode).toBe('ad')
    expect(profile.editable).toEqual({ name: false, email: false, phone: true, password: false })
  })

  it('needs a session', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.me.profile(), 401)
  })
})

describe('me.updateProfile (AC-10)', () => {
  it('changes the own name, email and phone, and auth.me shows the new name', async () => {
    const { gateway } = await localAs('kim')

    const profile = await gateway.me.updateProfile({ name: '김새이름', email: 'New@Corp.test', phone: '010-9999-8888' })

    expect(profile).toMatchObject({ name: '김새이름', email: 'new@corp.test', phone: '010-9999-8888' })
    expect((await gateway.auth.me()).name).toBe('김새이름')
  })

  it('never changes the id or the role', async () => {
    const { gateway } = await localAs('kim')

    const profile = await gateway.me.updateProfile({ name: '김새이름' })

    expect(profile).toMatchObject({ loginId: 'kim', role: 'sales' })
  })

  it('keeps omitted fields and clears a field given as null', async () => {
    const { gateway } = await localAs('kim')
    await gateway.me.updateProfile({ phone: '02-123-4567' })

    const profile = await gateway.me.updateProfile({ email: null, phone: null })

    expect(profile).toMatchObject({ name: '김영업', email: null, phone: null })
  })

  it.each([
    ['a blank name', { name: ' ' }, /이름/],
    ['an invalid email', { email: 'abc' }, '이메일 형식이 올바르지 않습니다.'],
    ['an invalid phone', { phone: '12' }, '전화번호 형식이 올바르지 않습니다.'],
  ])('rejects %s with 422 and changes nothing', async (_name, input, message) => {
    const { gateway } = await localAs('kim')

    await expectApiError(gateway.me.updateProfile(input), 422, message)

    expect(await gateway.me.profile()).toMatchObject({ name: '김영업', email: 'kim@neoine.test' })
  })

  it.each([{ name: '새 이름' }, { email: 'a@b.co' }])('refuses %j in AD mode with 409', async (input) => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.me.updateProfile(input), 409, AD_MANAGED)
  })

  it('lets the phone be changed in AD mode', async () => {
    const { gateway } = await mockAs('kim')

    const profile = await gateway.me.updateProfile({ phone: '010-1111-2222' })

    expect(profile.phone).toBe('010-1111-2222')
  })

  it('lets a read-only user edit the own profile', async () => {
    const { gateway } = await localAs('han')

    const profile = await gateway.me.updateProfile({ phone: '010-1111-2222' })

    expect(profile).toMatchObject({ role: 'user', phone: '010-1111-2222' })
  })

  it('needs a session', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.me.updateProfile({ phone: '02-123-4567' }), 401)
  })
})

describe('me.changePassword (AC-11)', () => {
  it('checks the current password, sets the new one and keeps the session', async () => {
    const { gateway } = await localAs('kim')

    await expect(gateway.me.changePassword(SEED_PASSWORD, NEW_PW)).resolves.toBeUndefined()

    expect((await gateway.auth.me()).loginId).toBe('kim')
    await gateway.auth.logout()
    await expectApiError(gateway.auth.login('kim', SEED_PASSWORD), 401)
    expect((await gateway.auth.login('kim', NEW_PW)).me).toMatchObject({ loginId: 'kim' })
  })

  it('rejects a wrong current password with 422 (not 401) and keeps the old password', async () => {
    const { gateway } = await localAs('kim')

    await expectApiError(gateway.me.changePassword('wrong-password-1', NEW_PW), 422, WRONG_CURRENT)

    expect((await gateway.auth.me()).loginId).toBe('kim')
    await gateway.auth.logout()
    expect((await gateway.auth.login('kim', SEED_PASSWORD)).me).toMatchObject({ loginId: 'kim' })
  })

  it.each(['short7!', 'kim'])('rejects the weak new password %s with 422', async (password) => {
    const { gateway } = await localAs('kim')

    await expectApiError(gateway.me.changePassword(SEED_PASSWORD, password), 422, WEAK)
  })

  it('refuses in AD mode with 409', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.me.changePassword('x', NEW_PW), 409, LOCAL_ONLY)
  })

  it('needs a session', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.me.changePassword('x', NEW_PW), 401)
  })
})
