import { afterEach, describe, expect, it, vi } from 'vitest'
import type { DirectorySettingsInput } from '../../shared/model/types'
import { json, problem, stubFetch, userRefBody } from './testHelpers'
import { createSettingsHttp } from './settings'

afterEach(() => vi.unstubAllGlobals())

const INPUT: DirectorySettingsInput = {
  serverUrls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test'],
  useStarttls: true,
  caCertPem: null,
  bindTemplate: 'CORP\\{login_id}',
  baseDn: 'dc=corp,dc=test',
  userFilter: '(sAMAccountName={login_id})',
  displayNameAttribute: 'displayName',
  emailAttribute: 'mail',
  connectTimeoutSeconds: 5,
  receiveTimeoutSeconds: 10,
}

const REQUEST_BODY = {
  server_urls: ['ldaps://dc1.corp.test', 'ldaps://dc2.corp.test'],
  use_starttls: true,
  ca_cert_pem: null,
  bind_template: 'CORP\\{login_id}',
  base_dn: 'dc=corp,dc=test',
  user_filter: '(sAMAccountName={login_id})',
  display_name_attribute: 'displayName',
  email_attribute: 'mail',
  connect_timeout_seconds: 5,
  receive_timeout_seconds: 10,
}

const STORED = {
  ...REQUEST_BODY,
  revision: 3,
  updated_at: '2026-10-15T10:00:00+09:00',
  updated_by: userRefBody('u1', '최관리'),
}

describe('directory settings over HTTP', () => {
  it('getDirectory maps the stored settings to camelCase', async () => {
    const { calls } = stubFetch(json(STORED))

    const settings = await createSettingsHttp().getDirectory()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/settings/directory' })
    expect(settings).toMatchObject({
      serverUrls: INPUT.serverUrls,
      useStarttls: true,
      bindTemplate: 'CORP\\{login_id}',
      baseDn: 'dc=corp,dc=test',
      revision: 3,
      updatedAt: '2026-10-15T10:00:00+09:00',
      updatedBy: { id: 'u1', name: '최관리' },
    })
  })

  it('getDirectory returns null when nothing is registered (404)', async () => {
    stubFetch(problem(404, 'not-found', 'AD 설정이 없습니다.'))

    await expect(createSettingsHttp().getDirectory()).resolves.toBeNull()
  })

  it('getDirectory still reports other failures such as 403', async () => {
    stubFetch(problem(403, 'forbidden', '권한이 없습니다.'))

    await expect(createSettingsHttp().getDirectory()).rejects.toMatchObject({ status: 403 })
  })

  it('saveDirectory puts the settings with the password and the expected revision', async () => {
    const { calls } = stubFetch(json({ ...STORED, revision: 4 }))

    const saved = await createSettingsHttp().saveDirectory(INPUT, { password: 'pw-root', expectedRevision: 3 })

    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: '/api/v1/settings/directory',
      body: { ...REQUEST_BODY, password: 'pw-root', expected_revision: 3 },
    })
    expect(saved.revision).toBe(4)
  })

  it('saveDirectory sends a null password for a dev-login admin', async () => {
    const { calls } = stubFetch(json(STORED))

    await createSettingsHttp().saveDirectory(INPUT, { password: null, expectedRevision: 3 })

    expect(calls[0]?.body).toMatchObject({ password: null, expected_revision: 3 })
  })

  it('saveDirectory shows the server message for a stale revision', async () => {
    stubFetch(problem(409, 'invalid-state', '다른 관리자가 먼저 설정을 바꿨습니다. 새로 고친 뒤 다시 시도하세요.'))

    await expect(createSettingsHttp().saveDirectory(INPUT, { password: 'x', expectedRevision: 1 })).rejects.toMatchObject({
      kind: 'conflict',
      message: '다른 관리자가 먼저 설정을 바꿨습니다. 새로 고친 뒤 다시 시도하세요.',
    })
  })

  it('testDirectory posts the settings with the password and resolves on success', async () => {
    const { calls } = stubFetch(json({ success: true, message: '연결에 성공했습니다.', stage: null }))

    await expect(createSettingsHttp().testDirectory(INPUT, 'pw-root')).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/settings/directory/test', body: { ...REQUEST_BODY, password: 'pw-root' } })
    expect(calls[0]?.body).not.toHaveProperty('expected_revision')
  })

  it('testDirectory turns success=false into a 422 directory-verification-failed with the stage', async () => {
    stubFetch(json({ success: false, message: '바인드에 실패했습니다.', stage: 'bind' }))

    const failure = createSettingsHttp().testDirectory(INPUT, null)

    await expect(failure).rejects.toMatchObject({
      status: 422,
      kind: 'directory-verification-failed',
      stage: 'bind',
      message: '바인드에 실패했습니다.',
    })
  })

  it('testDirectory also accepts the server answering with the problem document', async () => {
    stubFetch(problem(422, 'directory-verification-failed', '연결 단계 실패', { stage: 'connect' }))

    await expect(createSettingsHttp().testDirectory(INPUT, null)).rejects.toMatchObject({ kind: 'directory-verification-failed', stage: 'connect' })
  })
})

describe('storage settings (no server yet)', () => {
  it('getStorage reports nothing registered', async () => {
    await expect(createSettingsHttp().getStorage()).resolves.toBeNull()
  })

  it.each([
    ['saveStorage', (g: ReturnType<typeof createSettingsHttp>) => g.saveStorage('/data')],
    ['testStorage', (g: ReturnType<typeof createSettingsHttp>) => g.testStorage('/data')],
  ])('%s answers 501', async (_name, run) => {
    await expect(run(createSettingsHttp())).rejects.toMatchObject({ status: 501 })
  })
})
