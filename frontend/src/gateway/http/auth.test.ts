import { afterEach, describe, expect, it, vi } from 'vitest'
import { createAuthHttp } from './auth'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const PRINCIPAL = { user_id: 1, subject: 'kim', name: '김영업', role: 'sales', email: 'kim@corp.test' }
const ME = { id: 1, loginId: 'kim', name: '김영업', role: 'sales' }

describe('auth over HTTP', () => {
  // 내 정보는 GET /auth/me 응답을 화면 사용자로 바꾼다.
  // 테스트 코드: AU-085
  it('me reads GET /auth/me and renames user_id and subject', async () => {
    // given: /auth/me가 user_id·subject를 담은 응답을 준다
    const { calls } = stubFetch(json(PRINCIPAL))

    // when: me()를 부른다
    await expect(createAuthHttp().me()).resolves.toEqual(ME)

    // then: id·loginId·name·role로 바뀐 사용자이고 GET /auth/me로 요청했다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/me' })
  })

  // 로그인은 아이디·비밀번호를 POST하고 경고 없는 사용자를 돌려준다.
  // 테스트 코드: AU-085
  it('login posts the credentials and returns the signed-in user without a warning', async () => {
    // given: 로그인 응답이 경고 없이 사용자를 준다
    const { calls } = stubFetch(json({ ...PRINCIPAL, directory_warning: null }))

    // when: login()을 부른다
    await expect(createAuthHttp().login('kim', 'pw')).resolves.toEqual({ me: ME, directoryWarning: null })

    // then: 사용자와 null 경고를 돌려주고 POST /auth/login 본문에 login_id·password를 실었다
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/login', body: { login_id: 'kim', password: 'pw' } })
  })

  // 대체 로그인한 admin의 경고를 화면 값으로 옮긴다.
  // 테스트 코드: AU-085
  it('login maps the admin directory warning of a fallback login', async () => {
    // given: 로그인 응답이 connect 경고를 싣는다
    const message = 'AD 서버에 연결하지 못해 이전에 로그인한 비밀번호로 로그인했습니다.'
    stubFetch(json({ ...PRINCIPAL, role: 'admin', directory_warning: { stage: 'connect', message } }))

    // when: login()을 부른다
    await expect(createAuthHttp().login('kim', 'pw')).resolves.toEqual({
      // then: 사용자와 단계·문구가 있는 경고를 돌려준다
      me: { ...ME, role: 'admin' },
      directoryWarning: { stage: 'connect', message },
    })
  })

  // 경고 단계 여덟 가지를 그대로 옮긴다.
  // 테스트 코드: AU-085
  it.each(['not_configured', 'connect', 'tls', 'service_bind', 'base_dn', 'search', 'credential_unreadable', 'unknown'])(
    'login keeps the %s warning stage',
    async (stage) => {
      // given: 로그인 응답이 단계별 경고를 싣는다
      stubFetch(json({ ...PRINCIPAL, role: 'admin', directory_warning: { stage, message: '안내' } }))

      // when: login()을 부른다
      const result = await createAuthHttp().login('kim', 'pw')

      // then: 단계와 문구가 그대로다
      expect(result.directoryWarning).toEqual({ stage, message: '안내' })
    },
  )

  // 경고 키가 없는 응답은 경고 없음으로 본다.
  // 테스트 코드: AU-085
  it('login treats a response without the warning key as no warning', async () => {
    // given: 로그인 응답에 directory_warning 키가 없다
    stubFetch(json(PRINCIPAL))

    // when: login()을 부른다
    const result = await createAuthHttp().login('kim', 'pw')
    // then: directoryWarning이 null이다
    expect(result).toMatchObject({ directoryWarning: null })
  })

  // 로그인 실패 401은 unauthorized 종류와 서버 문구다.
  // 테스트 코드: AU-086
  it('shows the server message and the unauthorized kind for wrong credentials', async () => {
    // given: 서버가 401 공통 실패 문구를 준다
    stubFetch(problem(401, 'unauthenticated', '아이디 또는 비밀번호가 올바르지 않습니다.'))

    // when: login()을 부른다
    await expect(createAuthHttp().login('kim', 'bad')).rejects.toMatchObject({
      // then: status 401, kind unauthorized, 서버 문구가 그대로인 오류로 reject된다
      status: 401,
      kind: 'unauthorized',
      message: '아이디 또는 비밀번호가 올바르지 않습니다.',
    })
  })

  // 로그아웃은 POST /auth/logout이고 204를 성공으로 본다.
  // 테스트 코드: AU-087
  it('logout posts to /auth/logout and accepts 204', async () => {
    // given: 서버가 204를 준다
    const { calls } = stubFetch(noContent())

    // when: logout()을 부른다
    await expect(createAuthHttp().logout()).resolves.toBeUndefined()

    // then: 성공으로 끝나고 POST /auth/logout로 요청했다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/auth/logout' })
  })

  // 인증 설정은 설정 필요 여부와 방식만 노출한다.
  // 테스트 코드: AU-087
  it('config exposes only the setup state and auth mode, no quick login', async () => {
    // given: 설정이 끝난 ad 시스템의 설정 응답
    const { calls } = stubFetch(json({ directory_login: true, needs_admin_setup: false, needs_directory_setup: false, needs_storage_setup: false, auth_mode: 'ad' }))

    // when: config()를 부른다
    await expect(createAuthHttp().config()).resolves.toEqual({ needsSetup: false, authMode: 'ad' })

    // then: needsSetup false와 authMode ad뿐이고 GET /auth/config로 요청했다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/auth/config' })
  })

  // 세 단계 중 하나라도 남았으면 설정이 필요하다고 본다.
  // 테스트 코드: AU-087
  it.each([
    [true, false, false],
    [false, true, false],
    [false, false, true],
    [true, true, true],
  ])(
    'config needsSetup is true when directory=%s storage=%s or admin=%s setup is pending',
    async (directory, storage, admin) => {
      // given: AD·저장·admin 단계 중 일부가 남은 응답
      stubFetch(
        json({
          directory_login: true,
          needs_admin_setup: admin,
          needs_directory_setup: directory,
          needs_storage_setup: storage,
          auth_mode: 'ad',
        }),
      )

      // when: config()를 부른다
      const result = await createAuthHttp().config()
      // then: needsSetup이 true다
      expect(result).toEqual({ needsSetup: true, authMode: 'ad' })
    },
  )

  // auth_mode를 authMode로 옮긴다.
  // 테스트 코드: AU-087
  it.each([['local' as const], [null]])('config exposes auth_mode=%s as authMode', async (mode) => {
    // given: auth_mode가 local이거나 null인 응답
    stubFetch(json({ directory_login: false, needs_admin_setup: false, needs_directory_setup: false, needs_storage_setup: true, auth_mode: mode }))

    // when: config()를 부른다
    const result = await createAuthHttp().config()
    // then: authMode가 그 값이다
    expect(result).toEqual({ needsSetup: true, authMode: mode })
  })

  // auth_mode가 없는 응답은 아직 고르지 않은 것으로 본다.
  // 테스트 코드: AU-087
  it('config treats a response without auth_mode as no choice yet', async () => {
    // given: 응답에 auth_mode 키가 없다
    stubFetch(json({ directory_login: true, needs_admin_setup: false, needs_directory_setup: false, needs_storage_setup: false }))

    // when: config()를 부른다
    const result = await createAuthHttp().config()
    // then: authMode가 null이다
    expect(result).toMatchObject({ authMode: null })
  })

  // local 로그인 응답도 같은 모양(경고 없음)이다.
  // 테스트 코드: AU-085
  it('login keeps the local login response the same shape (no directory warning)', async () => {
    // given: local 로그인 응답
    stubFetch(json({ ...PRINCIPAL, directory_warning: null }))

    // when: login()을 부른다
    const result = await createAuthHttp().login('kim', 'Passw0rd-ok')
    // then: 사용자와 null 경고다
    expect(result).toEqual({ me: ME, directoryWarning: null })
  })
})
