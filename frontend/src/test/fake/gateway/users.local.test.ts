import { describe, expect, it } from 'vitest'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'
import { SEED_PASSWORD } from '../seed/users'
import { expectApiError, mockAs } from '../testing'

/** 서버 `POST /users`·`PATCH /users/{id}`·`PUT /users/{id}/password`와 같은 문구·판정 순서 (계획). */
const AD_MANAGED = 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다.'
const LOCAL_ONLY = '앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.'
const RESIGNED = '이미 퇴사 처리된 사용자입니다'
const WEAK = '비밀번호는 8자 이상이어야 합니다'
const PW = 'Passw0rd-ok'
const NEW_PW = 'Fresh-passw0rd'

async function localAdmin() {
  const mock = await mockAs('root')
  mock.control.setAuthMode('local')
  return mock
}

const NEW_USER = { loginId: 'newbie', name: '신입영업', role: 'sales' as const, password: PW, email: 'newbie@corp.test', phone: '010-1234-5678' }

describe('users.list phone', () => {
  // 전화번호가 없는 사용자는 phone이 null이다
  it('carries a null phone for users who have none', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when: 사용자 목록을 읽는다
    const users = await gateway.users.list('all')

    // then: 모든 항목의 phone이 null이다
    expect(users.every((u) => u.phone === null)).toBe(true)
  })
})

describe('users.create in local mode', () => {
  // local 방식 등록은 프로필·비밀번호를 저장하고 그 비밀번호로 로그인된다
  it('registers the user with profile and password, who can then sign in', async () => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when: 프로필과 비밀번호로 사용자를 등록한다
    const created = await gateway.users.create(NEW_USER)

    // then: 응답에 비밀번호가 없다
    expect(created).toMatchObject({ loginId: 'newbie', name: '신입영업', email: 'newbie@corp.test', phone: '010-1234-5678', status: 'active' })
    expect(JSON.stringify(created)).not.toContain(PW)
    // when: 로그아웃한 뒤 새 사용자가 그 비밀번호로 로그인한다
    await gateway.auth.logout()
    const login = await gateway.auth.login('newbie', PW)
    // then: 새 사용자로 로그인된다
    expect(login.me).toMatchObject({ loginId: 'newbie', role: 'sales' })
    // when·then: 틀린 비밀번호로 로그인한다 → 401이다
    await expectApiError(gateway.auth.login('newbie', 'wrong-password'), 401)
  })

  // 이메일·전화를 생략하면 null로 저장된다
  it('treats a missing email and phone as null', async () => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when: 이메일·전화 없이 등록한다
    const created = await gateway.users.create({ loginId: 'newbie', name: '신입영업', role: 'user', password: PW })

    // then: email과 phone이 null이다
    expect(created).toMatchObject({ email: null, phone: null })
  })

  // local 방식 등록의 잘못된 입력은 422이고 저장되지 않는다
  it.each([
    ['without a password', { password: undefined }, '비밀번호를 입력하세요.'],
    ['with a weak password', { password: 'short7!' }, WEAK],
    ['with the id as the password', { loginId: 'newbie.id', password: 'Newbie.Id' }, '비밀번호는 아이디와 같을 수 없습니다'],
    ['without a name', { name: ' ' }, '이름을 입력하세요.'],
    ['with an invalid email', { email: 'not-an-email' }, '이메일 형식이 올바르지 않습니다.'],
    ['with an invalid phone', { phone: '12' }, '전화번호 형식이 올바르지 않습니다.'],
  ])('rejects a registration %s with 422', async (_name, override, message) => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when·then: 비밀번호 누락·약함·아이디와 같음, 이름 없음, 이메일·전화 형식 오류로 등록한다 → 칸별 422 문구이고 사용자 목록에 새 사용자가 없다
    await expectApiError(gateway.users.create({ ...NEW_USER, ...override }), 422, message)

    expect((await gateway.users.list('all')).some((u) => u.loginId.startsWith('newbie'))).toBe(false)
  })

  // 이미 있는 아이디는 409다
  it('rejects an id already in use with 409', async () => {
    // given: local 방식의 admin이고 kim이 있다
    const { gateway } = await localAdmin()

    // when·then: kim으로 등록한다 → 중복 409 문구다
    await expectApiError(gateway.users.create({ ...NEW_USER, loginId: 'kim' }), 409, '이미 존재하는 사용자입니다: kim')
  })

  // local 방식에서 예약 아이디는 대소문자와 무관하게 422다
  it.each(['dev-admin', 'dev-sales', 'dev-user', 'DEV-Admin'])('rejects the reserved id %s with 422', async (loginId) => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when·then: 예약 아이디로 등록한다 → 개발 로그인 전용 아이디 422다
    await expectApiError(gateway.users.create({ ...NEW_USER, loginId }), 422, /개발 로그인 전용 아이디/)
  })

  // 예약 3개가 아닌 dev- 아이디는 일반 사용자로 등록된다
  it.each(['dev-ops', 'dev-qa', 'dev-admin2'])('registers the other dev- id %s as an ordinary user', async (loginId) => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when: dev-ops 같은 아이디로 등록한다
    const result = await gateway.users.create({ ...NEW_USER, loginId })

    // then: 재직 사용자로 등록된다
    expect(result).toMatchObject({ loginId, status: 'active' })
  })

  // 예약이 아닌 dev- 사용자의 비밀번호는 재설정된다
  it('resets the password of a dev- user that is not reserved (no 409)', async () => {
    // given: dev-ops를 등록했다
    const { gateway } = await localAdmin()
    // when: 그 사용자의 비밀번호를 재설정한다
    const user = await gateway.users.create({ ...NEW_USER, loginId: 'dev-ops' })

    // then: 409 없이 끝난다
    await expect(gateway.users.resetPassword(user.id, NEW_PW)).resolves.toBeUndefined()
  })
})

describe('users.create in AD mode', () => {
  // AD 방식에서도 예약 아이디는 422다
  it.each(['dev-admin', 'dev-sales', 'dev-user'])('rejects the reserved id %s with 422 in AD mode too', async (loginId) => {
    // given: AD 방식의 admin이다
    const { gateway } = await mockAs('root')

    // when·then: 예약 아이디로 등록한다 → 개발 로그인 전용 아이디 422다
    await expectApiError(gateway.users.create({ loginId, name: '개발', role: 'sales' }), 422, /개발 로그인 전용 아이디/)
  })

  // AD 방식에서 dev-ops는 등록된다
  it('registers dev-ops in AD mode', async () => {
    // given: AD 방식의 admin이다
    const { gateway } = await mockAs('root')

    // when: dev-ops로 등록한다
    const result = await gateway.users.create({ loginId: 'dev-ops', name: '운영', role: 'sales' })

    // then: 등록된다
    expect(result).toMatchObject({ loginId: 'dev-ops' })
  })

  // AD 방식에서 비밀번호를 보내면 422다
  it('rejects a password with 422', async () => {
    // given: AD 방식의 admin이다
    const { gateway } = await mockAs('root')

    // when·then: 비밀번호가 든 입력으로 등록한다 → 422다
    await expectApiError(gateway.users.create(NEW_USER), 422)
  })

  // AD 방식에서도 비밀번호 없이 전화·이메일은 받는다
  it('accepts phone and email without a password', async () => {
    // given: AD 방식의 admin이다
    const { gateway } = await mockAs('root')

    // when: 전화·이메일을 담아 등록한다
    const created = await gateway.users.create({ loginId: 'newbie', name: '신입영업', role: 'sales', phone: '010-1234-5678', email: 'n@corp.test' })

    // then: 전화·이메일이 저장된다
    expect(created).toMatchObject({ phone: '010-1234-5678', email: 'n@corp.test' })
  })
})

describe('users.update', () => {
  // local 방식에서 이름·이메일·전화를 고치면 정규화해 반영된다
  it('changes name, email and phone in local mode and returns the user', async () => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when: kim의 이름·이메일·전화를 고친다
    const changed = await gateway.users.update(USER_ID.kim, { name: '김새이름', email: 'New@Corp.test', phone: '02-123-4567' })

    // then: 새 값이 응답과 목록에 같고 이메일은 소문자이며 역할은 그대로다
    expect(changed).toMatchObject({ id: USER_ID.kim, loginId: 'kim', name: '김새이름', email: 'new@corp.test', phone: '02-123-4567', role: 'sales' })
    expect((await gateway.users.list('all')).find((u) => u.id === USER_ID.kim)).toEqual(changed)
  })

  // 보내지 않은 칸은 유지하고 null은 그 칸을 비운다
  it('keeps omitted fields and clears a field given as null', async () => {
    // given: kim에게 전화가 있다
    const { gateway } = await localAdmin()
    await gateway.users.update(USER_ID.kim, { phone: '02-123-4567' })

    // when: 전화를 null로 고친다
    const changed = await gateway.users.update(USER_ID.kim, { phone: null })

    // then: 전화만 비고 이름·이메일은 그대로다
    expect(changed).toMatchObject({ name: '김영업', email: 'kim@neoine.test', phone: null })
  })

  // 잘못된 이름·이메일·전화는 422이고 아무것도 바뀌지 않는다
  it.each([
    ['a blank name', { name: '' }, /이름/],
    ['an invalid email', { email: 'abc' }, '이메일 형식이 올바르지 않습니다.'],
    ['an invalid phone', { phone: '12' }, '전화번호 형식이 올바르지 않습니다.'],
  ])('rejects %s with 422 and changes nothing', async (_name, input, message) => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when·then: 빈 이름, 틀린 이메일, 틀린 전화로 고친다 → 422 문구이고 kim의 이름·이메일은 그대로다
    await expectApiError(gateway.users.update(USER_ID.kim, input), 422, message)

    expect((await gateway.users.list('all')).find((u) => u.id === USER_ID.kim)).toMatchObject({ name: '김영업', email: 'kim@neoine.test' })
  })

  // AD 방식에서는 이름·이메일 수정이 409다
  it.each([{ name: '새 이름' }, { email: 'a@b.co' }])('refuses %j in AD mode with 409', async (input) => {
    // given: AD 방식의 admin이다
    const { gateway } = await mockAs('root')

    // when·then: 이름 또는 이메일을 고친다 → AD 관리 문구의 409다
    await expectApiError(gateway.users.update(USER_ID.kim, input), 409, AD_MANAGED)
  })

  // AD 방식에서도 전화는 고칠 수 있다
  it('lets the phone be changed in AD mode', async () => {
    // given: AD 방식의 admin이다
    const { gateway } = await mockAs('root')

    // when: 전화를 고친다
    const changed = await gateway.users.update(USER_ID.kim, { phone: '02-123-4567' })

    // then: 전화가 바뀐다
    expect(changed.phone).toBe('02-123-4567')
  })

  // 퇴사자는 409, 없는 사용자는 404다
  it('refuses a resigned user with 409 and an unknown user with 404', async () => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when·then: 퇴사자와 없는 id의 정보를 고친다 → 퇴사자는 409, 없는 id는 404다
    await expectApiError(gateway.users.update(USER_ID.old, { phone: '02-123-4567' }), 409, RESIGNED)
    await expectApiError(gateway.users.update(NO_SUCH_ID, { phone: '02-123-4567' }), 404)
  })

  // 정보 수정은 admin만 가능하다
  it.each(['kim', 'han'] as const)('is admin only: %s gets 403', async (key) => {
    // given: sales 또는 user로 로그인했다
    const { gateway } = await mockAs(key)

    // when·then: 다른 사용자의 정보를 고친다 → 403이다
    await expectApiError(gateway.users.update(USER_ID.park, { phone: '02-123-4567' }), 403)
  })
})

describe('users.resetPassword', () => {
  // 비밀번호 재설정 뒤 새 비밀번호로만 로그인된다
  it('sets the new password: the user signs in with it and no longer with the old one', async () => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when: kim의 비밀번호를 재설정한다
    const result = await gateway.users.resetPassword(USER_ID.kim, NEW_PW)

    // then: 값 없이 끝난다
    expect(result).toBeUndefined()

    // when·then: 로그아웃한 뒤 옛 비밀번호로 로그인한다 → 401이다
    await gateway.auth.logout()
    await expectApiError(gateway.auth.login('kim', SEED_PASSWORD), 401)
    // when: 새 비밀번호로 로그인한다
    const login = await gateway.auth.login('kim', NEW_PW)
    // then: kim으로 로그인된다
    expect(login.me).toMatchObject({ loginId: 'kim' })
  })

  // AD 방식에서는 재설정이 409다
  it('refuses in AD mode with 409', async () => {
    // given: AD 방식의 admin이다
    const { gateway } = await mockAs('root')

    // when·then: 비밀번호를 재설정한다 → local 전용 문구의 409다
    await expectApiError(gateway.users.resetPassword(USER_ID.kim, NEW_PW), 409, LOCAL_ONLY)
  })

  // admin 자신의 비밀번호는 재설정할 수 없다
  it('refuses the admin own password with 409', async () => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when·then: 자기 자신의 비밀번호를 재설정한다 → 409다
    await expectApiError(gateway.users.resetPassword(USER_ID.root, NEW_PW), 409)
  })

  // 퇴사자 재설정은 409, 없는 사용자는 404다
  it('refuses a resigned user with 409 and an unknown user with 404', async () => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when·then: 퇴사자와 없는 id의 비밀번호를 재설정한다 → 퇴사자는 409, 없는 id는 404다
    await expectApiError(gateway.users.resetPassword(USER_ID.old, NEW_PW), 409, RESIGNED)
    await expectApiError(gateway.users.resetPassword(NO_SUCH_ID, NEW_PW), 404)
  })

  // 약한 비밀번호는 422이고 기존 비밀번호가 유지된다
  it('refuses a weak password with 422 and keeps the old one', async () => {
    // given: local 방식의 admin이다
    const { gateway } = await localAdmin()

    // when·then: 8자 미만 비밀번호로 재설정한다 → 422다
    await expectApiError(gateway.users.resetPassword(USER_ID.kim, 'short7!'), 422, WEAK)

    // when: 로그아웃한 뒤 옛 비밀번호로 로그인한다
    await gateway.auth.logout()
    const login = await gateway.auth.login('kim', SEED_PASSWORD)
    // then: 계속 로그인된다
    expect(login.me).toMatchObject({ loginId: 'kim' })
  })

  // 비밀번호 재설정은 admin만 가능하다
  it('is admin only: sales gets 403', async () => {
    // given: local 방식에서 sales로 로그인했다
    const { gateway, control } = await mockAs('kim')
    control.setAuthMode('local')

    // when·then: 다른 사용자의 비밀번호를 재설정한다 → 403이다
    await expectApiError(gateway.users.resetPassword(USER_ID.park, NEW_PW), 403)
  })
})
