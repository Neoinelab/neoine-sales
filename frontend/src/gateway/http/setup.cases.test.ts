import { afterEach, describe, expect, it, vi } from 'vitest'
import { DIRECTORY_INPUT } from '../../test/directoryFixtures'
import { createAuthHttp } from './auth'
import { createSetupHttp } from './setup'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const config = (needsDirectory: boolean, needsStorage: boolean, needsAdmin: boolean, authMode?: 'ad' | 'local' | null) =>
  json({
    directory_login: true,
    needs_admin_setup: needsAdmin,
    needs_directory_setup: needsDirectory,
    needs_storage_setup: needsStorage,
    ...(authMode === undefined ? {} : { auth_mode: authMode }),
  })

describe('최초 설정 HTTP 게이트웨이 (SU-043~SU-045)', () => {
  // HTTP 게이트웨이는 진행 상태를 세 단계 완료 여부와 방식으로 바꾼다.
  // 테스트 코드: SU-043
  it.each([
    [true, true, false, 'ad'],
    [true, false, false, 'ad'],
    [false, true, false, 'ad'],
    [false, false, true, 'ad'],
    [false, false, false, 'ad'],
    [true, true, false, null],
    [false, true, false, 'local'],
    [false, false, false, 'local'],
    [true, true, false, undefined],
  ] as const)(
    'maps needs_directory=%s needs_storage=%s needs_admin=%s auth_mode=%s to the step flags and needsSetup',
    async (nd, ns, na, mode) => {
      // given: /auth/config 응답의 needs_* 세 값과 auth_mode(키가 없는 경우 포함)
      stubFetch(config(nd, ns, na, mode), config(nd, ns, na, mode))

      // when: setup.status()와 auth.config()를 부른다
      const status = await createSetupHttp().status()
      const auth = await createAuthHttp().config()

      // then: directoryDone = !needs_directory, storageDone = !needs_storage, adminDone은 셋 다 false일 때만
      expect(status).toEqual({
        directoryDone: !nd,
        storageDone: !ns,
        adminDone: !(nd || ns || na),
        authMode: mode ?? null,
      })
      // then: needsSetup은 셋 중 하나라도 true면 true
      expect(auth.needsSetup).toBe(nd || ns || na)
    },
  )

  // 상태 조회는 GET /api/v1/auth/config를 부른다.
  // 테스트 코드: SU-043
  it('reads the progress from GET /api/v1/auth/config', async () => {
    // given: 새 시스템의 /auth/config 응답
    const { calls } = stubFetch(config(true, true, false, null))

    // when: setup.status()를 부른다
    await createSetupHttp().status()

    // then: GET /api/v1/auth/config 한 번
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/config' })
  })

  // 각 단계를 정해진 경로·본문으로 보낸다.
  // 테스트 코드: SU-044
  it('sends each step to its path with its body', async () => {
    // given: 서버가 모든 요청에 성공으로 답한다
    const admin = { user_id: 1, subject: 'root', name: 'root', role: 'admin', email: null }
    const boss = { user_id: 2, subject: 'boss', name: '보스', role: 'admin', email: 'boss@corp.test' }
    const { calls } = stubFetch(
      noContent(),
      json({}),
      json({ path: '/var/lib/neoine-sales/files', updated_at: '2026-10-17T09:30:00+09:00', updated_by: null }),
      noContent(),
      json(admin),
      json(boss),
      json(boss),
    )
    const setup = createSetupHttp()

    // when: 단계별 함수를 순서대로 부른다
    const chosen = await setup.chooseAuthMode('local')
    await setup.saveDirectory(DIRECTORY_INPUT)
    const saved = await setup.saveStorage('/var/lib/neoine-sales/files')
    const tested = await setup.testStorage('/data/files')
    const root = await setup.registerAdmin('root', 'pw')
    await setup.registerAdmin('boss', 'Passw0rd-ok', { name: '보스', email: 'boss@corp.test', phone: '02-123-4567' })
    await setup.registerAdmin('boss', 'Passw0rd-ok', { name: '보스', email: null, phone: null })

    // then: 경로·메서드·본문이 정해진 대로이고 204와 저장 응답은 undefined로 바뀐다
    expect([chosen, saved, tested]).toEqual([undefined, undefined, undefined])
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/auth/setup/auth-mode', body: { mode: 'local' } })
    expect(calls[1]).toMatchObject({ method: 'PUT', path: '/api/v1/auth/setup/directory' })
    expect(Object.keys(calls[1]?.body as object).sort()).toEqual(
      ['connect_timeout_seconds', 'host', 'port', 'security', 'test_token', 'user_filter'],
    )
    expect(calls[2]).toMatchObject({ method: 'PUT', path: '/api/v1/auth/setup/storage', body: { path: '/var/lib/neoine-sales/files' } })
    expect(calls[3]).toMatchObject({ method: 'POST', path: '/api/v1/auth/setup/storage/test', body: { path: '/data/files' } })
    expect(calls[4]).toMatchObject({ method: 'POST', path: '/api/v1/auth/setup', body: { login_id: 'root', password: 'pw' } })
    expect(root).toEqual({ id: 1, loginId: 'root', name: 'root', role: 'admin' })
    expect(calls[5]?.body).toEqual({
      login_id: 'boss',
      password: 'Passw0rd-ok',
      display_name: '보스',
      email: 'boss@corp.test',
      phone: '02-123-4567',
    })
    expect(calls[6]?.body).toEqual({ login_id: 'boss', password: 'Passw0rd-ok', display_name: '보스' })
  })

  // 서버 거절을 상태·문구·단계 그대로 넘긴다.
  // 테스트 코드: SU-045
  it.each([
    ['chooseAuthMode', 409, 'invalid-state', '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다', 'conflict'],
    ['saveStorage', 409, 'invalid-state', '먼저 인증 방식을 고르세요.', 'conflict'],
    ['saveStorage', 409, 'invalid-state', '먼저 AD 서버를 등록하세요', 'conflict'],
    ['saveStorage', 422, 'invalid-value', '해당 위치에 쓸 수 없습니다.', 'validation'],
    ['testStorage', 422, 'invalid-value', '절대 경로를 입력하세요.', 'validation'],
    ['registerAdmin', 409, 'invalid-state', '파일 저장 위치를 먼저 설정하세요.', 'conflict'],
  ] as const)('%s rejects with the server status, kind and message (%s %s)', async (method, status, serverKind, detail, kind) => {
    // given: 서버가 해당 오류로 답한다
    stubFetch(problem(status, serverKind, detail))
    const setup = createSetupHttp()

    // when: 해당 게이트웨이 함수를 부른다
    const call =
      method === 'chooseAuthMode'
        ? setup.chooseAuthMode('local')
        : method === 'registerAdmin'
          ? setup.registerAdmin('root', 'pw')
          : setup[method]('/x')

    // then: ApiError로 reject되고 상태·kind·서버 문구가 그대로다
    await expect(call).rejects.toMatchObject({ status, kind, message: detail })
  })

  // 확인 실패는 단계(stage)까지 그대로 넘긴다.
  // 테스트 코드: SU-045
  it('keeps the failed stage of a directory verification error', async () => {
    // given: 서버가 service_bind 단계의 확인 실패로 답한다
    stubFetch(problem(422, 'directory-verification-failed', '바인드 실패', { stage: 'service_bind' }))

    // when: AD 서버를 저장한다
    const call = createSetupHttp().saveDirectory(DIRECTORY_INPUT)

    // then: kind와 stage가 그대로다
    await expect(call).rejects.toMatchObject({ status: 422, kind: 'directory-verification-failed', stage: 'service_bind' })
  })
})

describe('최초 설정 연결 테스트 HTTP 게이트웨이 (SU-072)', () => {
  const SEVEN_KEYS = ['bind_account', 'bind_password', 'connect_timeout_seconds', 'host', 'port', 'security', 'user_filter']
  // 테스트 대상 메서드는 구현 전이라 타입에 없을 수 있어 느슨하게 부른다.
  type Testable = { testDirectory: (input: typeof DIRECTORY_INPUT) => Promise<{ baseDn: string }> }
  const testDirectory = () => (createSetupHttp() as unknown as Testable).testDirectory(DIRECTORY_INPUT)

  // 연결 테스트는 정해진 경로로 7칸을 보내고 성공이면 Base DN을 돌려준다.
  // 테스트 코드: SU-072
  it('posts the seven inputs to the test path and resolves with the found base DN', async () => {
    // given: 서버가 200 success=true와 Base DN으로 답한다
    const { calls } = stubFetch(json({ success: true, test_token: 'test-proof', stage: null, message: 'AD 설정을 확인했습니다', base_dn: 'dc=found,dc=test' }))

    // when: testDirectory를 부른다
    const result = await testDirectory()

    // then: POST /api/v1/auth/setup/directory/test에 snake_case 7키가 가고 Base DN이 돌아온다
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/setup/directory/test' })
    expect(Object.keys(calls[0]?.body as object).sort()).toEqual(SEVEN_KEYS)
    expect(result).toEqual({ baseDn: 'dc=found,dc=test', testToken: 'test-proof' })
  })

  // 200이어도 success=false이면 확인 실패 오류(422, 단계 포함)로 바꾼다.
  // 테스트 코드: SU-072
  it('turns a 200 failure result into a directory-verification-failed error with its stage', async () => {
    // given: 서버가 200 success=false(service_bind 단계)로 답한다
    stubFetch(json({ success: false, stage: 'service_bind', message: '서버 문구', base_dn: null }))

    // when: testDirectory를 부른다
    const call = testDirectory()

    // then: ApiError 422 directory-verification-failed, 서버 문구와 단계가 그대로다
    await expect(call).rejects.toMatchObject({ status: 422, kind: 'directory-verification-failed', message: '서버 문구', stage: 'service_bind' })
  })

  // 설정이 닫혔으면 409를 서버 문구 그대로 넘긴다.
  // 테스트 코드: SU-072
  it('rejects with the server 409 message when the setup is closed', async () => {
    // given: 서버가 409 invalid-state로 답한다
    stubFetch(problem(409, 'invalid-state', '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다'))

    // when: testDirectory를 부른다
    const call = testDirectory()

    // then: ApiError 409 conflict와 서버 문구
    await expect(call).rejects.toMatchObject({ status: 409, kind: 'conflict', message: '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다' })
  })
})
