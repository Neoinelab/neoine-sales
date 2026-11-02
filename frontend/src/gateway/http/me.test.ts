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
  it('profile reads GET /me/profile and renames the fields', async () => {
    const { calls } = stubFetch(json(profileBody()))

    await expect(createMeHttp().profile()).resolves.toEqual(PROFILE)

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/me/profile' })
  })

  it('profile maps an AD user: only the phone is editable', async () => {
    stubFetch(
      json(profileBody({ auth_mode: 'ad', phone: '02-123-4567', editable: { display_name: false, email: false, phone: true, password: false } })),
    )

    await expect(createMeHttp().profile()).resolves.toMatchObject({
      authMode: 'ad',
      phone: '02-123-4567',
      editable: { name: false, email: false, phone: true, password: false },
    })
  })

  it('profile uses the login id when the user has no display name', async () => {
    stubFetch(json(profileBody({ display_name: null })))

    await expect(createMeHttp().profile()).resolves.toMatchObject({ name: 'kim' })
  })

  it('profile shows the server message when not signed in', async () => {
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다'))

    await expect(createMeHttp().profile()).rejects.toMatchObject({ status: 401, kind: 'unauthorized', message: '로그인이 필요합니다' })
  })

  it('updateProfile sends PATCH /me/profile with only the given fields and returns the profile', async () => {
    const { calls } = stubFetch(json(profileBody({ display_name: '김새이름', phone: '010-9999-8888' })))

    const profile = await createMeHttp().updateProfile({ name: '김새이름', phone: '010-9999-8888' })

    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/me/profile' })
    expect(calls[0]?.body).toEqual({ display_name: '김새이름', phone: '010-9999-8888' })
    expect(profile).toMatchObject({ name: '김새이름', phone: '010-9999-8888' })
  })

  it('updateProfile sends null to clear a field', async () => {
    const { calls } = stubFetch(json(profileBody({ email: null })))

    await createMeHttp().updateProfile({ email: null })

    expect(calls[0]?.body).toEqual({ email: null })
  })

  it('updateProfile never sends the id or the role', async () => {
    const { calls } = stubFetch(json(profileBody()))

    await createMeHttp().updateProfile({ name: '김영업' })

    const keys = Object.keys(calls[0]?.body as object)
    expect(keys).not.toContain('login_id')
    expect(keys).not.toContain('role')
  })

  it.each([
    [409, 'invalid-state', 'AD 연동 사용자의 이름·이메일은 AD에서 관리합니다', 'conflict'],
    [422, 'invalid-value', '이메일 형식이 올바르지 않습니다.', 'validation'],
    [422, 'request-validation', '요청 형식이 올바르지 않습니다', 'validation'],
  ])('updateProfile shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createMeHttp().updateProfile({ name: 'x' })).rejects.toMatchObject({ status, kind, message: detail })
  })

  it('changePassword sends PUT /me/password with both passwords and resolves on 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createMeHttp().changePassword('old-password-1', 'Fresh-passw0rd')).resolves.toBeUndefined()

    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: '/api/v1/me/password',
      body: { current_password: 'old-password-1', new_password: 'Fresh-passw0rd' },
    })
  })

  it('changePassword reports a wrong current password as a validation error, not as a sign-out', async () => {
    stubFetch(problem(422, 'invalid-value', '현재 비밀번호가 올바르지 않습니다.'))

    await expect(createMeHttp().changePassword('bad', 'Fresh-passw0rd')).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '현재 비밀번호가 올바르지 않습니다.',
    })
  })

  it.each([
    [429, 'too-many-attempts', '로그인 시도가 너무 많습니다. 잠시 후 다시 시도하세요', 'too-many-attempts'],
    [409, 'invalid-state', '앱에서 계정을 직접 관리할 때만 쓸 수 있습니다.', 'conflict'],
    [422, 'invalid-value', '비밀번호는 8자 이상이어야 합니다.', 'validation'],
  ])('changePassword shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createMeHttp().changePassword('old', 'new')).rejects.toMatchObject({ status, kind, message: detail })
  })
})
