import { afterEach, describe, expect, it, vi } from 'vitest'
import { BIND_PASSWORD, DIRECTORY_INPUT } from '../../test/directoryFixtures'
import type { DirectorySettingsInput } from '../../shared/model/types'
import { json, noContent, problem, stubFetch } from './testHelpers'
import { createSetupHttp } from './setup'

afterEach(() => vi.unstubAllGlobals())

const config = (needsDirectory: boolean, needsStorage: boolean, needsAdmin: boolean, authMode: 'ad' | 'local' | null = 'ad') =>
  json({
    dev_login: false,
    directory_login: true,
    needs_admin_setup: needsAdmin,
    needs_directory_setup: needsDirectory,
    needs_storage_setup: needsStorage,
    auth_mode: authMode,
  })

const INPUT: DirectorySettingsInput = DIRECTORY_INPUT

describe('setup over HTTP', () => {
  // 서버는 AD 설정과 저장 위치가 모두 있을 때만 needs_admin_setup=true를 준다. 관리자가 없으면 세 값 중 하나는 true이므로
  // adminDone은 세 값이 모두 false일 때만 true다(AD·저장 단계가 남았는데 로그인 화면으로 보내면 안 된다).
  it.each([
    [true, true, false, { directoryDone: false, storageDone: false, adminDone: false, authMode: 'ad' }],
    [true, false, false, { directoryDone: false, storageDone: true, adminDone: false, authMode: 'ad' }],
    [false, true, false, { directoryDone: true, storageDone: false, adminDone: false, authMode: 'ad' }],
    [false, false, true, { directoryDone: true, storageDone: true, adminDone: false, authMode: 'ad' }],
    [false, false, false, { directoryDone: true, storageDone: true, adminDone: true, authMode: 'ad' }],
  ])(
    'status maps needs_directory_setup=%s needs_storage_setup=%s needs_admin_setup=%s to the three step flags',
    async (nd, ns, na, expected) => {
      const { calls } = stubFetch(config(nd, ns, na))

      await expect(createSetupHttp().status()).resolves.toEqual(expected)

      expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/config' })
    },
  )

  it.each([
    [true, true, false, null, { directoryDone: false, storageDone: false, adminDone: false, authMode: null }],
    [false, true, false, 'local', { directoryDone: true, storageDone: false, adminDone: false, authMode: 'local' }],
    [false, false, true, 'local', { directoryDone: true, storageDone: true, adminDone: false, authMode: 'local' }],
    [false, false, false, 'local', { directoryDone: true, storageDone: true, adminDone: true, authMode: 'local' }],
  ] as const)(
    'status carries auth_mode=%s (local mode never needs the directory step)',
    async (nd, ns, na, mode, expected) => {
      stubFetch(config(nd, ns, na, mode))

      await expect(createSetupHttp().status()).resolves.toEqual(expected)
    },
  )

  it('status treats a response without auth_mode as no choice yet', async () => {
    stubFetch(json({ dev_login: false, directory_login: false, needs_admin_setup: false, needs_directory_setup: true, needs_storage_setup: true }))

    await expect(createSetupHttp().status()).resolves.toMatchObject({ authMode: null })
  })

  it.each(['ad', 'local'] as const)('chooseAuthMode puts the mode %s to /auth/setup/auth-mode and resolves on 204', async (mode) => {
    const { calls } = stubFetch(noContent())

    await expect(createSetupHttp().chooseAuthMode(mode)).resolves.toBeUndefined()

    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/auth/setup/auth-mode', body: { mode } })
  })

  it('chooseAuthMode shows the server message once the first admin exists', async () => {
    stubFetch(problem(409, 'invalid-state', '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다'))

    await expect(createSetupHttp().chooseAuthMode('local')).rejects.toMatchObject({
      status: 409,
      kind: 'conflict',
      message: '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다',
    })
  })

  it('saveStorage shows the server message when no auth mode was chosen yet', async () => {
    stubFetch(problem(409, 'invalid-state', '먼저 인증 방식을 고르세요.'))

    await expect(createSetupHttp().saveStorage('/x')).rejects.toMatchObject({ kind: 'conflict', message: '먼저 인증 방식을 고르세요.' })
  })

  it('saveDirectory puts the seven snake_case fields (with the bind password) to /auth/setup/directory', async () => {
    const { calls } = stubFetch(json({}))

    await createSetupHttp().saveDirectory(INPUT)

    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: '/api/v1/auth/setup/directory',
      body: {
        host: 'dc1.corp.test',
        port: 636,
        security: 'ssl',
        bind_account: 'CORP\\svc-sales',
        bind_password: BIND_PASSWORD,
        user_filter: '(sAMAccountName={login_id})',
        connect_timeout_seconds: 5,
      },
    })
    expect(Object.keys(calls[0]?.body as object)).toHaveLength(7)
  })

  it('saveDirectory shows the failed stage of the verification', async () => {
    stubFetch(problem(422, 'directory-verification-failed', '바인드 실패', { stage: 'service_bind' }))

    await expect(createSetupHttp().saveDirectory(INPUT)).rejects.toMatchObject({
      status: 422,
      kind: 'directory-verification-failed',
      stage: 'service_bind',
    })
  })

  it('saveStorage puts the path to /auth/setup/storage and resolves with nothing', async () => {
    const { calls } = stubFetch(json({ path: '/var/lib/neoine-sales/files', updated_at: '2026-10-17T09:30:00+09:00', updated_by: null }))

    await expect(createSetupHttp().saveStorage('/var/lib/neoine-sales/files')).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/auth/setup/storage', body: { path: '/var/lib/neoine-sales/files' } })
  })

  it('testStorage posts the path to /auth/setup/storage/test and resolves on 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createSetupHttp().testStorage('/data/files')).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/setup/storage/test', body: { path: '/data/files' } })
  })

  it.each([
    ['saveStorage', 409, 'invalid-state', '먼저 AD 서버를 등록하세요', 'conflict'],
    ['saveStorage', 409, 'invalid-state', '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다', 'conflict'],
    ['saveStorage', 422, 'invalid-value', '해당 위치에 쓸 수 없습니다.', 'validation'],
    ['testStorage', 409, 'invalid-state', '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다', 'conflict'],
    ['testStorage', 422, 'invalid-value', '절대 경로를 입력하세요.', 'validation'],
  ] as const)('%s shows the server message "%s" (%s)', async (method, status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createSetupHttp()[method]('/x')).rejects.toMatchObject({ status, kind, message: detail })
  })

  it('registerAdmin shows the server message when no storage location is set yet', async () => {
    stubFetch(problem(409, 'invalid-state', '파일 저장 위치를 먼저 설정하세요.'))

    await expect(createSetupHttp().registerAdmin('root', 'pw')).rejects.toMatchObject({
      kind: 'conflict',
      message: '파일 저장 위치를 먼저 설정하세요.',
    })
  })

  it('registerAdmin posts to /auth/setup and returns the signed-in admin', async () => {
    const { calls } = stubFetch(json({ user_id: 1, subject: 'root', name: 'root', role: 'admin', email: null }))

    const me = await createSetupHttp().registerAdmin('root', 'pw')

    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/setup', body: { login_id: 'root', password: 'pw' } })
    expect(me).toEqual({ id: 1, loginId: 'root', name: 'root', role: 'admin' })
  })

  it('registerAdmin with a profile posts display_name, email and phone (local mode)', async () => {
    const { calls } = stubFetch(json({ user_id: 1, subject: 'boss', name: '보스', role: 'admin', email: 'boss@corp.test' }))

    const me = await createSetupHttp().registerAdmin('boss', 'Passw0rd-ok', { name: '보스', email: 'boss@corp.test', phone: '02-123-4567' })

    expect(calls[0]).toMatchObject({
      method: 'POST',
      path: '/api/v1/auth/setup',
      body: { login_id: 'boss', password: 'Passw0rd-ok', display_name: '보스', email: 'boss@corp.test', phone: '02-123-4567' },
    })
    expect(me).toEqual({ id: 1, loginId: 'boss', name: '보스', role: 'admin' })
  })

  it('registerAdmin leaves out an empty email and phone', async () => {
    const { calls } = stubFetch(json({ user_id: 1, subject: 'boss', name: '보스', role: 'admin', email: null }))

    await createSetupHttp().registerAdmin('boss', 'Passw0rd-ok', { name: '보스', email: null, phone: null })

    expect(calls[0]?.body).toEqual({ login_id: 'boss', password: 'Passw0rd-ok', display_name: '보스' })
  })

  it('registerAdmin without a profile still posts only the id and password (AD mode)', async () => {
    const { calls } = stubFetch(json({ user_id: 1, subject: 'root', name: 'root', role: 'admin', email: null }))

    await createSetupHttp().registerAdmin('root', 'pw')

    expect(calls[0]?.body).toEqual({ login_id: 'root', password: 'pw' })
  })

  it('registerAdmin shows the server message for a weak password', async () => {
    stubFetch(problem(422, 'invalid-value', '비밀번호는 8자 이상이어야 합니다.'))

    await expect(createSetupHttp().registerAdmin('boss', 'short', { name: '보스', email: null, phone: null })).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '비밀번호는 8자 이상이어야 합니다.',
    })
  })

  it('shows the server message when the setup is already done', async () => {
    stubFetch(problem(409, 'invalid-state', '이미 설정이 완료되었습니다.'))

    await expect(createSetupHttp().registerAdmin('root', 'pw')).rejects.toMatchObject({ kind: 'conflict', message: '이미 설정이 완료되었습니다.' })
  })
})
