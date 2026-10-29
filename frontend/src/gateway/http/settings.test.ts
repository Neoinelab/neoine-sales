import { afterEach, describe, expect, it, vi } from 'vitest'
import { BIND_PASSWORD, DIRECTORY_INPUT } from '../../test/directoryFixtures'
import type { DirectorySettingsInput } from '../../shared/model/types'
import { json, noContent, problem, stubFetch, userRefBody } from './testHelpers'
import { createSettingsHttp } from './settings'

afterEach(() => vi.unstubAllGlobals())

const INPUT: DirectorySettingsInput = DIRECTORY_INPUT

/** 서버 요청 본문: 입력 7개(snake_case). 구 필드(server_urls 등)는 없다. */
const REQUEST_BODY = {
  host: 'dc1.corp.test',
  port: 636,
  security: 'ssl',
  bind_account: 'CORP\\svc-sales',
  bind_password: BIND_PASSWORD,
  user_filter: '(sAMAccountName={login_id})',
  connect_timeout_seconds: 5,
}

const STORED = {
  host: 'dc1.corp.test',
  port: 636,
  security: 'ssl',
  bind_account: 'CORP\\svc-sales',
  bind_credential_status: 'ok',
  user_filter: '(sAMAccountName={login_id})',
  connect_timeout_seconds: 5,
  base_dn: 'dc=corp,dc=test',
  revision: 3,
  updated_at: '2026-10-15T10:00:00+09:00',
  updated_by: userRefBody(1, '최관리'),
}

describe('directory settings over HTTP', () => {
  it('getDirectory maps the stored settings to camelCase with the read-only Base DN and credential status', async () => {
    const { calls } = stubFetch(json(STORED))

    const settings = await createSettingsHttp().getDirectory()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/settings/directory' })
    expect(settings).toMatchObject({
      host: 'dc1.corp.test',
      port: 636,
      security: 'ssl',
      bindAccount: 'CORP\\svc-sales',
      bindCredentialStatus: 'ok',
      userFilter: '(sAMAccountName={login_id})',
      connectTimeoutSeconds: 5,
      baseDn: 'dc=corp,dc=test',
      revision: 3,
      updatedAt: '2026-10-15T10:00:00+09:00',
      updatedBy: { id: 1, name: '최관리' },
    })
    expect(JSON.stringify(settings)).not.toContain(BIND_PASSWORD)
  })

  it('getDirectory keeps the unreadable credential status', async () => {
    stubFetch(json({ ...STORED, bind_credential_status: 'unreadable' }))

    await expect(createSettingsHttp().getDirectory()).resolves.toMatchObject({ bindCredentialStatus: 'unreadable' })
  })

  it('getDirectory returns null when nothing is registered (404)', async () => {
    stubFetch(problem(404, 'not-found', 'AD 설정이 없습니다.'))

    await expect(createSettingsHttp().getDirectory()).resolves.toBeNull()
  })

  it('getDirectory still reports other failures such as 403', async () => {
    stubFetch(problem(403, 'forbidden', '권한이 없습니다.'))

    await expect(createSettingsHttp().getDirectory()).rejects.toMatchObject({ status: 403 })
  })

  it('saveDirectory puts the settings with the admin password and the expected revision', async () => {
    const { calls } = stubFetch(json({ ...STORED, revision: 4 }))

    const saved = await createSettingsHttp().saveDirectory(INPUT, { password: 'pw-root', expectedRevision: 3 })

    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: '/api/v1/settings/directory',
      body: { ...REQUEST_BODY, password: 'pw-root', expected_revision: 3 },
    })
    expect(saved.revision).toBe(4)
  })

  it('saveDirectory sends a null admin password for a dev-login admin', async () => {
    const { calls } = stubFetch(json(STORED))

    await createSettingsHttp().saveDirectory(INPUT, { password: null, expectedRevision: 3 })

    expect(calls[0]?.body).toMatchObject({ password: null, expected_revision: 3 })
  })

  it('saveDirectory leaves the bind_password key out when the stored password is kept (null)', async () => {
    const { calls } = stubFetch(json(STORED))

    await createSettingsHttp().saveDirectory({ ...INPUT, bindPassword: null }, { password: 'pw-root', expectedRevision: 3 })

    expect(calls[0]?.body).not.toHaveProperty('bind_password')
    expect(calls[0]?.body).toMatchObject({ host: 'dc1.corp.test', password: 'pw-root', expected_revision: 3 })
  })

  it('saveDirectory sends a null expected revision to create the first settings', async () => {
    const { calls } = stubFetch(json({ ...STORED, revision: 1 }))

    await createSettingsHttp().saveDirectory(INPUT, { password: null, expectedRevision: null })

    expect(calls[0]?.body).toMatchObject({ ...REQUEST_BODY, expected_revision: null })
  })

  it('saveDirectory sends only the seven input fields plus password and revision', async () => {
    const { calls } = stubFetch(json(STORED))

    await createSettingsHttp().saveDirectory(INPUT, { password: 'x', expectedRevision: 1 })

    expect(Object.keys(calls[0]?.body as object).sort()).toEqual(
      [...Object.keys(REQUEST_BODY), 'password', 'expected_revision'].sort(),
    )
  })

  it('saveDirectory shows the server message for a stale revision', async () => {
    stubFetch(problem(409, 'invalid-state', '다른 관리자가 먼저 설정을 바꿨습니다. 새로 고친 뒤 다시 시도하세요.'))

    await expect(createSettingsHttp().saveDirectory(INPUT, { password: 'x', expectedRevision: 1 })).rejects.toMatchObject({
      kind: 'conflict',
      message: '다른 관리자가 먼저 설정을 바꿨습니다. 새로 고친 뒤 다시 시도하세요.',
    })
  })

  it('testDirectory posts the settings with the password and resolves with the discovered Base DN', async () => {
    const { calls } = stubFetch(json({ success: true, message: '연결에 성공했습니다.', stage: null, base_dn: 'dc=corp,dc=test' }))

    await expect(createSettingsHttp().testDirectory(INPUT, 'pw-root')).resolves.toEqual({ baseDn: 'dc=corp,dc=test' })

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/settings/directory/test', body: { ...REQUEST_BODY, password: 'pw-root' } })
    expect(calls[0]?.body).not.toHaveProperty('expected_revision')
  })

  it('testDirectory leaves the bind_password key out when the stored password is kept', async () => {
    const { calls } = stubFetch(json({ success: true, message: 'ok', stage: null, base_dn: 'dc=a' }))

    await createSettingsHttp().testDirectory({ ...INPUT, bindPassword: null }, null)

    expect(calls[0]?.body).not.toHaveProperty('bind_password')
    expect(calls[0]?.body).toMatchObject({ host: 'dc1.corp.test', bind_account: 'CORP\\svc-sales', password: null })
  })

  it('testDirectory turns success=false into a 422 directory-verification-failed with the stage', async () => {
    stubFetch(json({ success: false, message: '바인드에 실패했습니다.', stage: 'bind', base_dn: null }))

    const failure = createSettingsHttp().testDirectory(INPUT, null)

    await expect(failure).rejects.toMatchObject({
      status: 422,
      kind: 'directory-verification-failed',
      stage: 'bind',
      message: '바인드에 실패했습니다.',
    })
  })

  it.each(['service_bind', 'base_dn', 'search'])('testDirectory keeps the %s stage of a failed result', async (stage) => {
    stubFetch(json({ success: false, message: '실패', stage, base_dn: null }))

    await expect(createSettingsHttp().testDirectory(INPUT, null)).rejects.toMatchObject({ kind: 'directory-verification-failed', stage })
  })

  it('testDirectory also accepts the server answering with the problem document', async () => {
    stubFetch(problem(422, 'directory-verification-failed', '연결 단계 실패', { stage: 'connect' }))

    await expect(createSettingsHttp().testDirectory(INPUT, null)).rejects.toMatchObject({ kind: 'directory-verification-failed', stage: 'connect' })
  })
})

const STORAGE_STORED = {
  path: '/var/lib/neoine-sales/files',
  updated_at: '2026-10-17T09:30:00+09:00',
  updated_by: userRefBody(1, '최관리', false, 'admin'),
}

describe('storage settings over HTTP', () => {
  it('getStorage maps the stored location to camelCase with who changed it', async () => {
    const { calls } = stubFetch(json(STORAGE_STORED))

    const storage = await createSettingsHttp().getStorage()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/settings/storage' })
    expect(storage).toEqual({
      path: '/var/lib/neoine-sales/files',
      updatedAt: '2026-10-17T09:30:00+09:00',
      updatedBy: { id: 1, name: '최관리', role: 'admin', status: 'active' },
    })
  })

  it('getStorage keeps updatedBy null when the location was registered by the first setup', async () => {
    stubFetch(json({ ...STORAGE_STORED, updated_by: null }))

    await expect(createSettingsHttp().getStorage()).resolves.toMatchObject({ updatedBy: null })
  })

  it('getStorage returns null when nothing is registered (404)', async () => {
    stubFetch(problem(404, 'not-found', '파일 저장 위치가 설정되지 않았습니다.'))

    await expect(createSettingsHttp().getStorage()).resolves.toBeNull()
  })

  it('getStorage still reports other failures such as 403', async () => {
    stubFetch(problem(403, 'forbidden', '관리자 권한이 필요합니다'))

    await expect(createSettingsHttp().getStorage()).rejects.toMatchObject({ status: 403, message: '관리자 권한이 필요합니다' })
  })

  it('saveStorage puts the path and returns the saved location', async () => {
    const { calls } = stubFetch(json({ ...STORAGE_STORED, path: '/data/files-v2' }))

    const saved = await createSettingsHttp().saveStorage('/data/files-v2')

    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/settings/storage', body: { path: '/data/files-v2' } })
    expect(saved).toMatchObject({ path: '/data/files-v2', updatedBy: { id: 1 } })
  })

  it.each([
    ['절대 경로를 입력하세요.'],
    ['해당 위치에 쓸 수 없습니다.'],
    ['저장 경로는 1024자 이내로 입력하세요.'],
  ])('saveStorage shows the server message %s as a validation error', async (detail) => {
    stubFetch(problem(422, 'invalid-value', detail))

    await expect(createSettingsHttp().saveStorage('x')).rejects.toMatchObject({ status: 422, kind: 'validation', message: detail })
  })

  it('testStorage posts the path and resolves on 204 without saving', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createSettingsHttp().testStorage('/data/files')).resolves.toBeUndefined()

    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/settings/storage/test', body: { path: '/data/files' } })
  })

  it('testStorage shows the server message for an unwritable location', async () => {
    stubFetch(problem(422, 'invalid-value', '해당 위치에 쓸 수 없습니다.'))

    await expect(createSettingsHttp().testStorage('/readonly')).rejects.toMatchObject({
      status: 422,
      message: '해당 위치에 쓸 수 없습니다.',
    })
  })
})
