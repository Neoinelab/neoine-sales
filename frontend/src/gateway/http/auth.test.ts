import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAuthHttp } from './auth'
import { json, noContent, problem, stubFetch } from './testHelpers'
import { NO_SUCH_ID, USER_ID } from '../../test/fake/seed/ids'

afterEach(() => vi.unstubAllGlobals())

const PRINCIPAL = { user_id: 1, subject: 'kim', name: '김영업', role: 'sales', email: 'kim@corp.test' }
const ME = { id: 1, loginId: 'kim', name: '김영업', role: 'sales' }

describe('auth over HTTP', () => {
  it('me reads GET /auth/me and renames user_id and subject', async () => {
    const { calls } = stubFetch(json(PRINCIPAL))

    await expect(createAuthHttp().me()).resolves.toEqual(ME)

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/me' })
  })

  it('login posts the credentials and returns the signed-in user without a warning', async () => {
    const { calls } = stubFetch(json({ ...PRINCIPAL, directory_warning: null }))

    await expect(createAuthHttp().login('kim', 'pw')).resolves.toEqual({ me: ME, directoryWarning: null })

    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/login', body: { login_id: 'kim', password: 'pw' } })
  })

  it('login maps the admin directory warning of a fallback login', async () => {
    const message = 'AD 서버에 연결하지 못해 이전에 로그인한 비밀번호로 로그인했습니다.'
    stubFetch(json({ ...PRINCIPAL, role: 'admin', directory_warning: { stage: 'connect', message } }))

    await expect(createAuthHttp().login('kim', 'pw')).resolves.toEqual({
      me: { ...ME, role: 'admin' },
      directoryWarning: { stage: 'connect', message },
    })
  })

  it.each(['not_configured', 'connect', 'tls', 'service_bind', 'base_dn', 'search', 'credential_unreadable', 'unknown'])(
    'login keeps the %s warning stage',
    async (stage) => {
      stubFetch(json({ ...PRINCIPAL, role: 'admin', directory_warning: { stage, message: '안내' } }))

      const result = await createAuthHttp().login('kim', 'pw')

      expect(result.directoryWarning).toEqual({ stage, message: '안내' })
    },
  )

  it('login treats a response without the warning key as no warning', async () => {
    stubFetch(json(PRINCIPAL))

    await expect(createAuthHttp().login('kim', 'pw')).resolves.toMatchObject({ directoryWarning: null })
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
    [USER_ID.root, 'admin'],
    [USER_ID.kim, 'sales'],
    [USER_ID.han, 'user'],
  ])('quickLogin(%s) posts dev-login with the role %s', async (userId, role) => {
    const { calls } = stubFetch(json({ ...PRINCIPAL, role }))

    const me = await createAuthHttp().quickLogin(userId)

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/dev-login', body: { role } })
    expect(me.role).toBe(role)
  })

  it('quickLogin refuses an unknown quick-login id without calling the server', async () => {
    const { calls } = stubFetch()

    await expect(createAuthHttp().quickLogin(NO_SUCH_ID)).rejects.toMatchObject({ status: 401, kind: 'unauthorized' })

    expect(calls).toHaveLength(0)
  })

  it('quickLogin shows the server error when dev login is switched off', async () => {
    stubFetch(problem(404, 'not-found', 'Not Found'))

    await expect(createAuthHttp().quickLogin(USER_ID.root)).rejects.toMatchObject({ status: 404 })
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
