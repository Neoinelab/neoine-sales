import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAuthHttp } from './auth'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const PRINCIPAL = { user_id: 'uuid-1', subject: 'kim', name: '김영업', role: 'sales', email: 'kim@corp.test' }
const ME = { id: 'uuid-1', loginId: 'kim', name: '김영업', role: 'sales' }

describe('auth over HTTP', () => {
  it('me reads GET /auth/me and renames user_id and subject', async () => {
    const { calls } = stubFetch(json(PRINCIPAL))

    await expect(createAuthHttp().me()).resolves.toEqual(ME)

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/me' })
  })

  it('login posts the credentials and returns the signed-in user', async () => {
    const { calls } = stubFetch(json(PRINCIPAL))

    await expect(createAuthHttp().login('kim', 'pw')).resolves.toEqual(ME)

    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/login', body: { login_id: 'kim', password: 'pw' } })
  })

  it('shows the server message and the unauthorized kind for wrong credentials', async () => {
    stubFetch(problem(401, 'unauthenticated', '아이디 또는 비밀번호가 올바르지 않습니다.'))

    await expect(createAuthHttp().login('kim', 'bad')).rejects.toMatchObject({
      status: 401,
      kind: 'unauthorized',
      message: '아이디 또는 비밀번호가 올바르지 않습니다.',
    })
  })

  it.each([
    ['u-root', 'admin'],
    ['u-kim', 'sales'],
    ['u-han', 'user'],
  ])('quickLogin(%s) posts dev-login with the role %s', async (userId, role) => {
    const { calls } = stubFetch(json({ ...PRINCIPAL, role }))

    const me = await createAuthHttp().quickLogin(userId)

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/dev-login', body: { role } })
    expect(me.role).toBe(role)
  })

  it('quickLogin refuses an unknown quick-login id without calling the server', async () => {
    const { calls } = stubFetch()

    await expect(createAuthHttp().quickLogin('u-nobody')).rejects.toMatchObject({ status: 401, kind: 'unauthorized' })

    expect(calls).toHaveLength(0)
  })

  it('quickLogin shows the server error when dev login is switched off', async () => {
    stubFetch(problem(404, 'not-found', 'Not Found'))

    await expect(createAuthHttp().quickLogin('u-root')).rejects.toMatchObject({ status: 404 })
  })

  it('logout posts to /auth/logout and accepts 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createAuthHttp().logout()).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/logout' })
  })

  it.each([true, false])('config exposes dev_login=%s as quickLogin', async (devLogin) => {
    const { calls } = stubFetch(json({ dev_login: devLogin, directory_login: true, needs_admin_setup: false, needs_directory_setup: false, needs_storage_setup: false }))

    await expect(createAuthHttp().config()).resolves.toEqual({ quickLogin: devLogin, needsSetup: false })

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/config' })
  })

  it.each([
    [true, false, false],
    [false, true, false],
    [false, false, true],
    [true, true, true],
  ])(
    'config needsSetup is true when directory=%s storage=%s or admin=%s setup is pending',
    async (directory, storage, admin) => {
      stubFetch(
        json({
          dev_login: false,
          directory_login: true,
          needs_admin_setup: admin,
          needs_directory_setup: directory,
          needs_storage_setup: storage,
        }),
      )

      await expect(createAuthHttp().config()).resolves.toEqual({ quickLogin: false, needsSetup: true })
    },
  )
})
