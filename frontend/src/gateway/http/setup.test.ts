import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DirectorySettingsInput } from '../../shared/model/types'
import { json, problem, stubFetch } from './testHelpers'
import { createSetupHttp } from './setup'

afterEach(() => vi.unstubAllGlobals())

const config = (needsDirectory: boolean, needsAdmin: boolean) =>
  json({ dev_login: false, directory_login: true, needs_admin_setup: needsAdmin, needs_directory_setup: needsDirectory })

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
  it.each([
    [true, true, { directoryDone: false, storageDone: true, adminDone: false }],
    [false, true, { directoryDone: true, storageDone: true, adminDone: false }],
    [false, false, { directoryDone: true, storageDone: true, adminDone: true }],
  ])('status maps needs_directory_setup=%s needs_admin_setup=%s and treats the storage step as done', async (nd, na, expected) => {
    const { calls } = stubFetch(config(nd, na))

    await expect(createSetupHttp().status()).resolves.toEqual(expected)

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/config' })
  })

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
