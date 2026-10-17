import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DirectorySettingsInput } from '../../shared/model/types'
import { json, noContent, problem, stubFetch } from './testHelpers'
import { createSetupHttp } from './setup'

afterEach(() => vi.unstubAllGlobals())

const config = (needsDirectory: boolean, needsStorage: boolean, needsAdmin: boolean) =>
  json({
    dev_login: false,
    directory_login: true,
    needs_admin_setup: needsAdmin,
    needs_directory_setup: needsDirectory,
    needs_storage_setup: needsStorage,
  })

const INPUT: DirectorySettingsInput = {
  serverUrls: ['ldaps://dc1.corp.test'],
  useStarttls: false,
  caCertPem: null,
  bindTemplate: 'CORP\\{login_id}',
  baseDn: 'dc=corp,dc=test',
  userFilter: '(sAMAccountName={login_id})',
  displayNameAttribute: 'displayName',
  emailAttribute: 'mail',
  connectTimeoutSeconds: 5,
  receiveTimeoutSeconds: 10,
}

describe('setup over HTTP', () => {
  // 서버는 AD 설정과 저장 위치가 모두 있을 때만 needs_admin_setup=true를 준다. 관리자가 없으면 세 값 중 하나는 true이므로
  // adminDone은 세 값이 모두 false일 때만 true다(AD·저장 단계가 남았는데 로그인 화면으로 보내면 안 된다).
  it.each([
    [true, true, false, { directoryDone: false, storageDone: false, adminDone: false }],
    [true, false, false, { directoryDone: false, storageDone: true, adminDone: false }],
    [false, true, false, { directoryDone: true, storageDone: false, adminDone: false }],
    [false, false, true, { directoryDone: true, storageDone: true, adminDone: false }],
    [false, false, false, { directoryDone: true, storageDone: true, adminDone: true }],
  ])(
    'status maps needs_directory_setup=%s needs_storage_setup=%s needs_admin_setup=%s to the three step flags',
    async (nd, ns, na, expected) => {
      const { calls } = stubFetch(config(nd, ns, na))

      await expect(createSetupHttp().status()).resolves.toEqual(expected)

      expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/config' })
    },
  )

  it('saveDirectory puts the snake_case settings to /auth/setup/directory', async () => {
    const { calls } = stubFetch(json({}))

    await createSetupHttp().saveDirectory(INPUT)

    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: '/api/v1/auth/setup/directory',
      body: {
        server_urls: ['ldaps://dc1.corp.test'],
        use_starttls: false,
        ca_cert_pem: null,
        bind_template: 'CORP\\{login_id}',
        base_dn: 'dc=corp,dc=test',
        user_filter: '(sAMAccountName={login_id})',
        display_name_attribute: 'displayName',
        email_attribute: 'mail',
        connect_timeout_seconds: 5,
        receive_timeout_seconds: 10,
      },
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
    const { calls } = stubFetch(json({ user_id: 'u1', subject: 'root', name: 'root', role: 'admin', email: null }))

    const me = await createSetupHttp().registerAdmin('root', 'pw')

    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/setup', body: { login_id: 'root', password: 'pw' } })
    expect(me).toEqual({ id: 'u1', loginId: 'root', name: 'root', role: 'admin' })
  })

  it('shows the server message when the setup is already done', async () => {
    stubFetch(problem(409, 'invalid-state', '이미 설정이 완료되었습니다.'))

    await expect(createSetupHttp().registerAdmin('root', 'pw')).rejects.toMatchObject({ kind: 'conflict', message: '이미 설정이 완료되었습니다.' })
  })
})
