import { describe, expect, it } from 'vitest'
import { SEED_PASSWORD } from '../seed/users'
import { expectApiError, mockAs } from '../testing'

/** 서버 `GET·PATCH /me/profile`·`PUT /me/password`와 같은 문구·판정 순서 (내 정보 ME-R19). */
const AD_MANAGED = 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다.'
const LOCAL_ONLY = '앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.'
const WRONG_CURRENT = '현재 비밀번호가 올바르지 않습니다.'
const WEAK = '비밀번호는 8자 이상이어야 합니다'
const BODY_INVALID = '요청 형식이 올바르지 않습니다'
const NEW_PW = 'Fresh-passw0rd'

async function localAs(key: 'root' | 'kim' | 'han') {
  const mock = await mockAs(key)
  mock.control.setAuthMode('local')
  return mock
}

describe('me.profile', () => {
  // local 모드에서 세 역할 모두 자기 정보와 모든 항목 수정 가능 표시를 받는다.
  // 테스트 코드: ME-055
  it.each([
    ['root', 'admin'],
    ['kim', 'sales'],
    ['han', 'user'],
  ] as const)('shows the %s profile with every field editable in local mode', async (key, role) => {
    // given: local 모드에서 해당 사용자로 로그인
    const { gateway } = await localAs(key)

    // when: profile()을 부른다
    const profile = await gateway.me.profile()

    // then: 아이디·역할·모드가 맞고 editable 네 값이 모두 true다
    expect(profile).toMatchObject({ loginId: key, role, authMode: 'local', phone: null })
    expect(profile.email).toBe(`${key}@neoine.test`)
    expect(profile.editable).toEqual({ name: true, email: true, phone: true, password: true })
  })

  // AD 모드에서는 전화만 수정할 수 있다.
  // 테스트 코드: ME-055
  it('allows only the phone in AD mode and no password change', async () => {
    // given: AD 모드의 kim
    const { gateway } = await mockAs('kim')

    // when: profile()을 부른다
    const profile = await gateway.me.profile()

    // then: authMode는 ad이고 editable은 전화만 true다
    expect(profile.authMode).toBe('ad')
    expect(profile.editable).toEqual({ name: false, email: false, phone: true, password: false })
  })

  // 세션이 없으면 401이다.
  // 테스트 코드: ME-055
  it('needs a session', async () => {
    // given: 세션 없음
    const { gateway } = await mockAs(null)

    // when·then: profile()을 부른다 → 401 ApiError로 reject한다
    await expectApiError(gateway.me.profile(), 401)
  })
})

describe('me.updateProfile', () => {
  // 이름·이메일·전화를 고치면 auth.me에도 새 이름이 보인다.
  // 테스트 코드: ME-056
  it('changes the own name, email and phone, and auth.me shows the new name', async () => {
    // given: local 모드의 kim
    const { gateway } = await localAs('kim')

    // when: 이름·이메일(대문자 섞음)·전화를 고친다
    const profile = await gateway.me.updateProfile({ name: '김새이름', email: 'New@Corp.test', phone: '010-9999-8888' })

    // then: 이메일은 소문자로 저장되고 auth.me의 이름이 바뀐다
    expect(profile).toMatchObject({ name: '김새이름', email: 'new@corp.test', phone: '010-9999-8888' })
    expect((await gateway.auth.me()).name).toBe('김새이름')
  })

  // 아이디와 역할은 바뀌지 않는다.
  // 테스트 코드: ME-056
  it('never changes the id or the role', async () => {
    // given: local 모드의 kim
    const { gateway } = await localAs('kim')

    // when: 이름을 고친다
    const profile = await gateway.me.updateProfile({ name: '김새이름' })

    // then: 아이디 kim, 역할 sales 그대로다
    expect(profile).toMatchObject({ loginId: 'kim', role: 'sales' })
  })

  // 주지 않은 키는 그대로이고 null은 값을 비운다.
  // 테스트 코드: ME-056
  it('keeps omitted fields and clears a field given as null', async () => {
    // given: local 모드의 kim이 전화를 가지고 있다
    const { gateway } = await localAs('kim')
    await gateway.me.updateProfile({ phone: '02-123-4567' })

    // when: 이메일과 전화를 null로 보낸다
    const profile = await gateway.me.updateProfile({ email: null, phone: null })

    // then: 이름은 그대로, 이메일·전화는 null이다
    expect(profile).toMatchObject({ name: '김영업', email: null, phone: null })
  })

  // 틀린 값은 422로 거절하고 아무것도 바꾸지 않는다.
  // 테스트 코드: ME-056
  it.each([
    ['a blank name', { name: ' ' }, '이름은(는) 비어 있을 수 없습니다'],
    ['an invalid email', { email: 'abc' }, '이메일 형식이 올바르지 않습니다.'],
    ['an invalid phone', { phone: '12' }, '전화번호 형식이 올바르지 않습니다.'],
  ])('rejects %s with 422 and changes nothing', async (_name, input, message) => {
    // given: local 모드의 kim
    const { gateway } = await localAs('kim')

    // when·then: 틀린 값으로 고친다 → 서버 문구의 422이고 저장된 값은 그대로다
    await expectApiError(gateway.me.updateProfile(input), 422, message)
    expect(await gateway.me.profile()).toMatchObject({ name: '김영업', email: 'kim@neoine.test' })
  })

  // AD 모드에서 이름·이메일을 고치려 하면 409다.
  // 테스트 코드: ME-056
  it.each([{ name: '새 이름' }, { email: 'a@b.co' }])('refuses %j in AD mode with 409', async (input) => {
    // given: AD 모드의 kim
    const { gateway } = await mockAs('kim')

    // when·then: 이름 또는 이메일을 고친다 → 409 AD 관리 문구다
    await expectApiError(gateway.me.updateProfile(input), 409, AD_MANAGED)
  })

  // AD 모드에서도 전화는 고칠 수 있다.
  // 테스트 코드: ME-056
  it('lets the phone be changed in AD mode', async () => {
    // given: AD 모드의 kim
    const { gateway } = await mockAs('kim')

    // when: 전화를 고친다
    const profile = await gateway.me.updateProfile({ phone: '010-1111-2222' })

    // then: 전화가 바뀐다
    expect(profile.phone).toBe('010-1111-2222')
  })

  // 읽기 전용 user 역할도 자기 정보를 고칠 수 있다.
  // 테스트 코드: ME-056
  it('lets a read-only user edit the own profile', async () => {
    // given: local 모드의 han(user)
    const { gateway } = await localAs('han')

    // when: 전화를 고친다
    const profile = await gateway.me.updateProfile({ phone: '010-1111-2222' })

    // then: 역할 user이고 전화가 바뀐다
    expect(profile).toMatchObject({ role: 'user', phone: '010-1111-2222' })
  })

  // 세션이 없으면 401이다.
  // 테스트 코드: ME-056
  it('needs a session', async () => {
    // given: 세션 없음
    const { gateway } = await mockAs(null)

    // when·then: 전화를 고친다 → 401이다
    await expectApiError(gateway.me.updateProfile({ phone: '02-123-4567' }), 401)
  })
})

describe('me.changePassword', () => {
  // 현재 비밀번호를 확인하고 새 비밀번호를 저장하며 세션은 유지한다.
  // 테스트 코드: ME-057
  it('checks the current password, sets the new one and keeps the session', async () => {
    // given: local 모드의 kim
    const { gateway } = await localAs('kim')

    // when: 맞는 현재 비밀번호로 바꾼다
    await expect(gateway.me.changePassword(SEED_PASSWORD, NEW_PW)).resolves.toBeUndefined()

    // then: 세션은 유지되고 새 비밀번호로만 로그인된다
    expect((await gateway.auth.me()).loginId).toBe('kim')
    await gateway.auth.logout()
    await expectApiError(gateway.auth.login('kim', SEED_PASSWORD), 401)
    expect((await gateway.auth.login('kim', NEW_PW)).me).toMatchObject({ loginId: 'kim' })
  })

  // 현재 비밀번호가 틀리면 401이 아니라 422이고 이전 비밀번호가 유지된다.
  // 테스트 코드: ME-057
  it('rejects a wrong current password with 422 (not 401) and keeps the old password', async () => {
    // given: local 모드의 kim
    const { gateway } = await localAs('kim')

    // when·then: 틀린 현재 비밀번호로 바꾼다 → 422 문구이고 세션·이전 비밀번호는 그대로다
    await expectApiError(gateway.me.changePassword('wrong-password-1', NEW_PW), 422, WRONG_CURRENT)
    expect((await gateway.auth.me()).loginId).toBe('kim')
    await gateway.auth.logout()
    expect((await gateway.auth.login('kim', SEED_PASSWORD)).me).toMatchObject({ loginId: 'kim' })
  })

  // 약한 새 비밀번호는 422다.
  // 테스트 코드: ME-057
  it.each(['short7!', 'kim'])('rejects the weak new password %s with 422', async (password) => {
    // given: local 모드의 kim
    const { gateway } = await localAs('kim')

    // when·then: 8자 미만 새 비밀번호로 바꾼다 → 422 길이 문구다
    await expectApiError(gateway.me.changePassword(SEED_PASSWORD, password), 422, WEAK)
  })

  // 257자 새 비밀번호는 서버처럼 요청 형식 오류(422)로 거절한다.
  // 테스트 코드: ME-057
  it('rejects a 257 character new password as a malformed request', async () => {
    // given: local 모드의 kim
    const { gateway } = await localAs('kim')

    // when·then: 257자 새 비밀번호로 바꾼다 → 422 요청 형식 문구다
    await expectApiError(gateway.me.changePassword(SEED_PASSWORD, 'a'.repeat(257)), 422, BODY_INVALID)
  })

  // AD 모드에서는 409다.
  // 테스트 코드: ME-057
  it('refuses in AD mode with 409', async () => {
    // given: AD 모드의 kim
    const { gateway } = await mockAs('kim')

    // when·then: 비밀번호를 바꾼다 → 409 local 전용 문구다
    await expectApiError(gateway.me.changePassword('x', NEW_PW), 409, LOCAL_ONLY)
  })

  // 세션이 없으면 401이다.
  // 테스트 코드: ME-057
  it('needs a session', async () => {
    // given: 세션 없음
    const { gateway } = await mockAs(null)

    // when·then: 비밀번호를 바꾼다 → 401이다
    await expectApiError(gateway.me.changePassword('x', NEW_PW), 401)
  })
})
