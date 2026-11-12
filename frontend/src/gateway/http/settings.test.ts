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
  // AD 설정 조회 응답을 camelCase로 바꾸고 읽기 전용 Base DN·비밀번호 상태를 담는다.
  // 테스트 코드: IN-080
  it('getDirectory maps the stored settings to camelCase with the read-only Base DN and credential status', async () => {
    // given: 서버가 AD 설정 200 응답을 준다
    const { calls } = stubFetch(json(STORED))

    // when: HTTP 게이트웨이로 조회한다
    const settings = await createSettingsHttp().getDirectory()

    // then: camelCase 값(bindCredentialStatus, baseDn, updatedBy)이다
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

  // 읽을 수 없음 상태를 그대로 전한다.
  // 테스트 코드: IN-080
  it('getDirectory keeps the unreadable credential status', async () => {
    // given: 서버가 unreadable 상태를 준다
    stubFetch(json({ ...STORED, bind_credential_status: 'unreadable' }))

    // when: 조회한다
    const result = await createSettingsHttp().getDirectory()

    // then: bindCredentialStatus가 unreadable이다
    expect(result).toMatchObject({ bindCredentialStatus: 'unreadable' })
  })

  // AD 설정 조회가 404면 오류가 아니라 null이다.
  // 테스트 코드: IN-080
  it('getDirectory returns null when nothing is registered (404)', async () => {
    // given: 서버가 404를 준다
    stubFetch(problem(404, 'not-found', 'AD 설정이 없습니다.'))

    // when: 조회한다
    const result = await createSettingsHttp().getDirectory()

    // then: null로 끝난다
    expect(result).toBeNull()
  })

  // 404 외의 실패는 그대로 던진다.
  // 테스트 코드: IN-080
  it('getDirectory still reports other failures such as 403', async () => {
    // given: 서버가 403을 준다
    stubFetch(problem(403, 'forbidden', '권한이 없습니다.'))

    // when·then: 조회한다 → ApiError 403으로 reject된다
    await expect(createSettingsHttp().getDirectory()).rejects.toMatchObject({ status: 403 })
  })

  // 저장은 입력 7칸과 현재 admin 비밀번호·읽은 revision을 PUT한다.
  // 테스트 코드: IN-082
  it('saveDirectory puts the settings with the admin password and the expected revision', async () => {
    // when: 비밀번호와 revision으로 저장한다
    const { calls } = stubFetch(json({ ...STORED, revision: 4 }))

    const saved = await createSettingsHttp().saveDirectory(INPUT, { password: 'pw-root', expectedRevision: 3 })

    // then: 본문에 그 값이 실리고 저장 결과를 돌려준다
    expect(calls[0]).toMatchObject({
      method: 'PUT',
      path: '/api/v1/settings/directory',
      body: { ...REQUEST_BODY, password: 'pw-root', expected_revision: 3 },
    })
    expect(saved.revision).toBe(4)
  })

  // 비운 admin 비밀번호는 null로 보낸다.
  // 테스트 코드: IN-082
  it('saveDirectory sends a null admin password when it was left empty', async () => {
    // when: 비밀번호 null로 저장한다
    const { calls } = stubFetch(json(STORED))

    await createSettingsHttp().saveDirectory(INPUT, { password: null, expectedRevision: 3 })

    // then: 본문 password가 null이다
    expect(calls[0]?.body).toMatchObject({ password: null, expected_revision: 3 })
  })

  // 바인드 비밀번호 유지(null)면 bind_password 키를 보내지 않는다.
  // 테스트 코드: IN-082
  it('saveDirectory leaves the bind_password key out when the stored password is kept (null)', async () => {
    // when: 바인드 비밀번호 null로 저장한다
    const { calls } = stubFetch(json(STORED))

    await createSettingsHttp().saveDirectory({ ...INPUT, bindPassword: null }, { password: 'pw-root', expectedRevision: 3 })

    // then: 본문에 bind_password 키가 없다
    expect(calls[0]?.body).not.toHaveProperty('bind_password')
    expect(calls[0]?.body).toMatchObject({ host: 'dc1.corp.test', password: 'pw-root', expected_revision: 3 })
  })

  // 처음 만들 때는 expected_revision null을 보낸다.
  // 테스트 코드: IN-082
  it('saveDirectory sends a null expected revision to create the first settings', async () => {
    // when: revision null로 저장한다
    const { calls } = stubFetch(json({ ...STORED, revision: 1 }))

    await createSettingsHttp().saveDirectory(INPUT, { password: null, expectedRevision: null })

    // then: 본문 expected_revision이 null이다
    expect(calls[0]?.body).toMatchObject({ ...REQUEST_BODY, expected_revision: null })
  })

  // 저장 본문은 입력 7칸과 password·revision뿐이다.
  // 테스트 코드: IN-082
  it('saveDirectory sends only the seven input fields plus password and revision', async () => {
    // when: 저장한다
    const { calls } = stubFetch(json(STORED))

    await createSettingsHttp().saveDirectory(INPUT, { password: 'x', expectedRevision: 1 })

    // then: 본문 키가 그 집합뿐이다
    expect(Object.keys(calls[0]?.body as object).sort()).toEqual(
      [...Object.keys(REQUEST_BODY), 'password', 'expected_revision'].sort(),
    )
  })

  // 낡은 버전으로 저장하면 서버 문구의 충돌 오류로 거절한다.
  it('saveDirectory shows the server message for a stale revision', async () => {
    // given: 서버가 409 충돌 문구를 준다
    stubFetch(problem(409, 'invalid-state', '다른 관리자가 먼저 설정을 바꿨습니다. 새로 고친 뒤 다시 시도하세요.'))
    // when·then: 낡은 revision으로 AD 설정을 저장한다 → conflict 오류와 서버 문구다
    await expect(createSettingsHttp().saveDirectory(INPUT, { password: 'x', expectedRevision: 1 })).rejects.toMatchObject({
      kind: 'conflict',
      message: '다른 관리자가 먼저 설정을 바꿨습니다. 새로 고친 뒤 다시 시도하세요.',
    })
  })

  // 연결 테스트는 입력 7칸과 password를 POST하고 찾은 Base DN으로 끝난다.
  // 테스트 코드: IN-081, IN-082
  it('testDirectory posts the settings with the password and resolves with the discovered Base DN', async () => {
    // given: 서버가 success true 결과를 준다
    const { calls } = stubFetch(json({ success: true, message: '연결에 성공했습니다.', stage: null, base_dn: 'dc=corp,dc=test' }))

    // when: 연결 테스트한다
    const result = await createSettingsHttp().testDirectory(INPUT, 'pw-root')

    // then: {baseDn}으로 끝나고 본문에 expected_revision이 없다
    expect(result).toEqual({ baseDn: 'dc=corp,dc=test' })

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/settings/directory/test', body: { ...REQUEST_BODY, password: 'pw-root' } })
    expect(calls[0]?.body).not.toHaveProperty('expected_revision')
  })

  // 연결 테스트도 유지면 bind_password 키를 보내지 않는다.
  // 테스트 코드: IN-082
  it('testDirectory leaves the bind_password key out when the stored password is kept', async () => {
    // when: 바인드 비밀번호 null로 테스트한다
    const { calls } = stubFetch(json({ success: true, message: 'ok', stage: null, base_dn: 'dc=a' }))

    await createSettingsHttp().testDirectory({ ...INPUT, bindPassword: null }, null)

    // then: 본문에 bind_password 키가 없다
    expect(calls[0]?.body).not.toHaveProperty('bind_password')
    expect(calls[0]?.body).toMatchObject({ host: 'dc1.corp.test', bind_account: 'CORP\\svc-sales', password: null })
  })

  // 실패 결과(success false)는 단계를 가진 422 오류가 된다.
  // 테스트 코드: IN-081
  it('testDirectory turns success=false into a 422 directory-verification-failed with the stage', async () => {
    // given: 서버가 success false·stage·message를 준다
    stubFetch(json({ success: false, message: '바인드에 실패했습니다.', stage: 'bind', base_dn: null }))

    // when: 연결 테스트한다
    const failure = createSettingsHttp().testDirectory(INPUT, null)

    // then: ApiError 422 directory-verification-failed에 stage와 서버 문구가 있다
    await expect(failure).rejects.toMatchObject({
      status: 422,
      kind: 'directory-verification-failed',
      stage: 'bind',
      message: '바인드에 실패했습니다.',
    })
  })

  // 실패 결과의 단계를 그대로 유지한다.
  // 테스트 코드: IN-081
  it.each(['service_bind', 'base_dn', 'search'])('testDirectory keeps the %s stage of a failed result', async (stage) => {
    // given: 서버가 단계가 든 실패 결과를 준다
    stubFetch(json({ success: false, message: '실패', stage, base_dn: null }))

    // when·then: 연결 테스트한다 → 오류의 stage가 그 단계다
    await expect(createSettingsHttp().testDirectory(INPUT, null)).rejects.toMatchObject({ kind: 'directory-verification-failed', stage })
  })

  // 서버가 422 Problem으로 답해도 같은 종류로 받는다.
  // 테스트 코드: IN-081
  it('testDirectory also accepts the server answering with the problem document', async () => {
    // given: 서버가 422 directory-verification-failed Problem을 준다
    stubFetch(problem(422, 'directory-verification-failed', '연결 단계 실패', { stage: 'connect' }))

    // when·then: 연결 테스트한다 → 같은 kind의 오류로 reject된다
    await expect(createSettingsHttp().testDirectory(INPUT, null)).rejects.toMatchObject({ kind: 'directory-verification-failed', stage: 'connect' })
  })
})

const STORAGE_STORED = {
  path: '/var/lib/neoine-sales/files',
  updated_at: '2026-10-17T09:30:00+09:00',
  updated_by: userRefBody(1, '최관리', false, 'admin'),
}

describe('storage settings over HTTP', () => {
  // 저장 위치 조회 응답을 camelCase로 바꾸고 저장자를 담는다.
  // 테스트 코드: IN-080
  it('getStorage maps the stored location to camelCase with who changed it', async () => {
    // given: 서버가 저장 위치 200 응답을 준다
    const { calls } = stubFetch(json(STORAGE_STORED))

    // when: 조회한다
    const storage = await createSettingsHttp().getStorage()

    // then: path·updatedAt·updatedBy 값이다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/settings/storage' })
    expect(storage).toEqual({
      path: '/var/lib/neoine-sales/files',
      updatedAt: '2026-10-17T09:30:00+09:00',
      updatedBy: { id: 1, name: '최관리', role: 'admin', status: 'active' },
    })
  })

  // 최초 설정으로 저장된 위치는 저장자가 null이다.
  // 테스트 코드: IN-080
  it('getStorage keeps updatedBy null when the location was registered by the first setup', async () => {
    // given: 서버가 updated_by null을 준다
    stubFetch(json({ ...STORAGE_STORED, updated_by: null }))

    // when: 조회한다
    const result = await createSettingsHttp().getStorage()

    // then: updatedBy가 null이다
    expect(result).toMatchObject({ updatedBy: null })
  })

  // 저장 위치 조회가 404면 null이다.
  // 테스트 코드: IN-080
  it('getStorage returns null when nothing is registered (404)', async () => {
    // given: 서버가 404를 준다
    stubFetch(problem(404, 'not-found', '파일 저장 위치가 설정되지 않았습니다.'))

    // when: 조회한다
    const result = await createSettingsHttp().getStorage()

    // then: null로 끝난다
    expect(result).toBeNull()
  })

  // 저장 위치 조회의 404 외 실패는 그대로 던진다.
  // 테스트 코드: IN-080
  it('getStorage still reports other failures such as 403', async () => {
    // given: 서버가 403을 준다
    stubFetch(problem(403, 'forbidden', '관리자 권한이 필요합니다'))

    // when·then: 조회한다 → ApiError 403으로 reject된다
    await expect(createSettingsHttp().getStorage()).rejects.toMatchObject({ status: 403, message: '관리자 권한이 필요합니다' })
  })

  // 저장 위치 저장은 {path}를 PUT하고 저장 결과를 돌려준다.
  // 테스트 코드: IN-082
  it('saveStorage puts the path and returns the saved location', async () => {
    // when: 경로를 저장한다
    const { calls } = stubFetch(json({ ...STORAGE_STORED, path: '/data/files-v2' }))

    const saved = await createSettingsHttp().saveStorage('/data/files-v2')

    // then: PUT /settings/storage 본문이 {path}이고 결과가 반환된다
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/settings/storage', body: { path: '/data/files-v2' } })
    expect(saved).toMatchObject({ path: '/data/files-v2', updatedBy: { id: 1 } })
  })

  // 저장 위치 저장 오류는 서버 문구를 검증 오류로 보인다.
  it.each([
    ['절대 경로를 입력하세요.'],
    ['해당 위치에 쓸 수 없습니다.'],
    ['저장 경로는 1024자 이내로 입력하세요.'],
  ])('saveStorage shows the server message %s as a validation error', async (detail) => {
    // given: 서버가 422 문구를 준다
    stubFetch(problem(422, 'invalid-value', detail))

    // when·then: 저장 위치를 저장한다 → 검증 오류와 서버 문구로 reject한다
    await expect(createSettingsHttp().saveStorage('x')).rejects.toMatchObject({ status: 422, kind: 'validation', message: detail })
  })

  // 쓰기 테스트는 {path}를 POST하고 204를 성공으로 받는다.
  // 테스트 코드: IN-082
  it('testStorage posts the path and resolves on 204 without saving', async () => {
    // given: 서버가 204를 준다
    const { calls } = stubFetch(noContent())

    // when: 쓰기 테스트한다
    const result = await createSettingsHttp().testStorage('/data/files')

    // then: reject 없이 끝나고 요청은 한 번뿐이다
    expect(result).toBeUndefined()

    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/settings/storage/test', body: { path: '/data/files' } })
  })

  // 쓸 수 없는 저장 위치 테스트는 서버 문구의 422로 거절한다.
  it('testStorage shows the server message for an unwritable location', async () => {
    // given: 서버가 422 문구를 준다
    stubFetch(problem(422, 'invalid-value', '해당 위치에 쓸 수 없습니다.'))
    // when·then: 쓸 수 없는 위치로 저장 위치를 테스트한다 → 422 오류와 서버 문구다
    await expect(createSettingsHttp().testStorage('/readonly')).rejects.toMatchObject({
      status: 422,
      message: '해당 위치에 쓸 수 없습니다.',
    })
  })
})
