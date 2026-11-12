import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMeHttp } from './me'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const profileBody = (over: Record<string, unknown> = {}) => ({
  id: 2,
  login_id: 'kim',
  role: 'sales',
  display_name: '김영업',
  email: 'kim@corp.test',
  phone: null,
  auth_mode: 'local',
  editable: { display_name: true, email: true, phone: true, password: true },
  ...over,
})

const PROFILE = {
  id: 2,
  loginId: 'kim',
  role: 'sales',
  name: '김영업',
  email: 'kim@corp.test',
  phone: null,
  authMode: 'local',
  editable: { name: true, email: true, phone: true, password: true },
}

describe('me over HTTP (내 정보)', () => {
  // profile은 GET /me/profile 응답을 화면 모델로 바꾼다.
  // 테스트 코드: ME-055
  it('profile reads GET /me/profile and renames the fields', async () => {
    // given: 서버가 local 사용자 정보를 준다
    const { calls } = stubFetch(json(profileBody()))

    // when: profile()을 부른다
    const result = await createMeHttp().profile()
    // then: 화면 모델(name, loginId, editable.name)로 바뀌고 GET /api/v1/me/profile을 불렀다
    expect(result).toEqual(PROFILE)
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/me/profile' })
  })

  // AD 사용자는 editable이 전화만 true다.
  // 테스트 코드: ME-055
  it('profile maps an AD user: only the phone is editable', async () => {
    // given: 서버가 AD 사용자 정보를 준다
    stubFetch(
      json(profileBody({ auth_mode: 'ad', phone: '02-123-4567', editable: { display_name: false, email: false, phone: true, password: false } })),
    )

    // when: profile()을 부른다
    const result = await createMeHttp().profile()
    // then: authMode ad, editable은 전화만 true다
    expect(result).toMatchObject({
      authMode: 'ad',
      phone: '02-123-4567',
      editable: { name: false, email: false, phone: true, password: false },
    })
  })

  // 이름이 없으면 name은 아이디다.
  // 테스트 코드: ME-055
  it('profile uses the login id when the user has no display name', async () => {
    // given: 서버가 display_name null을 준다
    stubFetch(json(profileBody({ display_name: null })))

    // when: profile()을 부른다
    const result = await createMeHttp().profile()
    // then: name은 아이디 kim이다
    expect(result).toMatchObject({ name: 'kim' })
  })

  // 로그인하지 않으면 서버 문구의 ApiError로 reject한다.
  // 테스트 코드: ME-055
  it('profile shows the server message when not signed in', async () => {
    // given: 서버가 401을 준다
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다'))

    // when·then: profile()을 부른다 → 401 ApiError와 서버 문구로 reject한다
    await expect(createMeHttp().profile()).rejects.toMatchObject({ status: 401, kind: 'unauthorized', message: '로그인이 필요합니다' })
  })

  // updateProfile은 준 키만 PATCH로 보내고 응답을 화면 모델로 바꾼다.
  // 테스트 코드: ME-056
  it('updateProfile sends PATCH /me/profile with only the given fields and returns the profile', async () => {
    // given: 서버가 바뀐 정보를 준다
    const { calls } = stubFetch(json(profileBody({ display_name: '김새이름', phone: '010-9999-8888' })))

    // when: updateProfile({ name, phone })을 부른다
    const profile = await createMeHttp().updateProfile({ name: '김새이름', phone: '010-9999-8888' })

    // then: PATCH 본문에는 display_name·phone만 실리고 응답이 화면 모델로 바뀐다
    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/me/profile' })
    expect(calls[0]?.body).toEqual({ display_name: '김새이름', phone: '010-9999-8888' })
    expect(profile).toMatchObject({ name: '김새이름', phone: '010-9999-8888' })
  })

  // null은 그대로 null로 보내 값을 비운다.
  // 테스트 코드: ME-056
  it('updateProfile sends null to clear a field', async () => {
    // given: 서버가 이메일이 빈 정보를 준다
    const { calls } = stubFetch(json(profileBody({ email: null })))

    // when: updateProfile({ email: null })을 부른다
    await createMeHttp().updateProfile({ email: null })

    // then: 본문은 { email: null }이다
    expect(calls[0]?.body).toEqual({ email: null })
  })

  // id·login_id·role은 보내지 않는다.
  // 테스트 코드: ME-056
  it('updateProfile never sends the id or the role', async () => {
    // given: 서버가 정보를 준다
    const { calls } = stubFetch(json(profileBody()))

    // when: updateProfile({ name })을 부른다
    await createMeHttp().updateProfile({ name: '김영업' })

    // then: 본문 키에 login_id·role·id가 없다
    const keys = Object.keys(calls[0]?.body as object)
    expect(keys).not.toContain('login_id')
    expect(keys).not.toContain('role')
    expect(keys).not.toContain('id')
  })

  // 서버 오류는 상태·detail을 그대로 가진 ApiError로 넘긴다.
  // 테스트 코드: ME-056
  it.each([
    [409, 'invalid-state', 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다.', 'conflict'],
    [422, 'invalid-value', '이메일 형식이 올바르지 않습니다.', 'validation'],
    [422, 'request-validation', '요청 형식이 올바르지 않습니다', 'validation'],
  ])('updateProfile shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 오류를 준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: updateProfile을 부른다 → 상태·kind·서버 문구를 가진 ApiError로 reject한다
    await expect(createMeHttp().updateProfile({ name: 'x' })).rejects.toMatchObject({ status, kind, message: detail })
  })

  // changePassword는 PUT /me/password를 보내고 204면 undefined로 끝난다.
  // 테스트 코드: ME-057
  it('changePassword sends PUT /me/password with both passwords and resolves on 204', async () => {
    // given: 서버가 204를 준다
    const { calls } = stubFetch(noContent())

    // when: changePassword를 부른다
    const result = await createMeHttp().changePassword('old-password-1', 'Fresh-passw0rd')
    // then: undefined로 끝나고 PUT 본문은 { current_password, new_password }다
    expect(result).toBeUndefined()
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: '/api/v1/me/password',
      body: { current_password: 'old-password-1', new_password: 'Fresh-passw0rd' },
    })
  })

  // 현재 비밀번호가 틀린 422는 로그아웃이 아니라 검증 오류로 넘긴다.
  // 테스트 코드: ME-057
  it('changePassword reports a wrong current password as a validation error, not as a sign-out', async () => {
    // given: 서버가 422 현재 비밀번호 틀림을 준다
    stubFetch(problem(422, 'invalid-value', '현재 비밀번호가 올바르지 않습니다.'))

    // when·then: changePassword를 부른다 → kind는 validation(unauthorized 아님)이다
    await expect(createMeHttp().changePassword('bad', 'Fresh-passw0rd')).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '현재 비밀번호가 올바르지 않습니다.',
    })
  })

  // 429·409·422 오류는 상태·detail을 그대로 넘긴다.
  // 테스트 코드: ME-057
  it.each([
    [429, 'too-many-attempts', '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요', 'too-many-attempts'],
    [409, 'invalid-state', '앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.', 'conflict'],
    [422, 'invalid-value', '비밀번호는 8자 이상이어야 합니다', 'validation'],
  ])('changePassword shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 오류를 준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: changePassword를 부른다 → 상태·kind·서버 문구를 가진 ApiError로 reject한다
    await expect(createMeHttp().changePassword('old', 'new')).rejects.toMatchObject({ status, kind, message: detail })
  })
})
