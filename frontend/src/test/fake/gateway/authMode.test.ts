import { describe, expect, it } from 'vitest'
import { DIRECTORY_INPUT } from '../../directoryFixtures'
import { emptyBusinessSeed } from '../seed'
import { SEED_PASSWORD } from '../seed/users'
import { expectApiError, mockAs, newMock } from '../testing'

/** 서버와 같은 문구·판정 순서를 지키는 Fake: 인증 방식 선택과 local 최초 설정·로그인 (계획 AC-1~5). */
const AUTH_MODE_FIRST = '먼저 인증 방식을 고르세요.'
const AD_FIRST = '먼저 AD 서버를 등록하세요'
const CLOSED = '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다'
const LOGIN_FAILED = '아이디 또는 비밀번호가 올바르지 않습니다.'
const PROFILE = { name: '보스', email: 'boss@corp.test', phone: '02-123-4567' }
const PW = 'Passw0rd-ok'

/** 최초 설정이 처음 상태인 mock. */
function freshMock() {
  const mock = newMock()
  mock.control.restartSetup()
  return mock
}

describe('setup.chooseAuthMode (AC-1·3)', () => {
  it('records local mode: no directory step is needed and the storage step is next', async () => {
    const { gateway } = freshMock()

    await expect(gateway.setup.chooseAuthMode('local')).resolves.toBeUndefined()

    expect(await gateway.setup.status()).toEqual({ authMode: 'local', directoryDone: true, storageDone: false, adminDone: false })
    expect(await gateway.auth.config()).toMatchObject({ authMode: 'local', needsSetup: true })
  })

  it('records the AD mode but still needs the AD server', async () => {
    const { gateway } = freshMock()

    await gateway.setup.chooseAuthMode('ad')

    expect(await gateway.setup.status()).toEqual({ authMode: 'ad', directoryDone: false, storageDone: false, adminDone: false })
  })

  it('can be chosen again until the first admin exists', async () => {
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('local')

    await gateway.setup.chooseAuthMode('ad')

    expect(await gateway.setup.status()).toMatchObject({ authMode: 'ad', directoryDone: false })
  })

  it('switches to the AD mode when the directory is saved after choosing local', async () => {
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('local')

    await gateway.setup.saveDirectory(DIRECTORY_INPUT)

    expect(await gateway.setup.status()).toMatchObject({ authMode: 'ad', directoryDone: true })
  })

  it('is refused with 409 once the first admin exists, for both modes', async () => {
    const { gateway } = newMock()

    await expectApiError(gateway.setup.chooseAuthMode('local'), 409, CLOSED)
    await expectApiError(gateway.setup.chooseAuthMode('ad'), 409, CLOSED)
    expect((await gateway.setup.status()).authMode).toBe('ad')
  })

  it('is public: it works without a session', async () => {
    const mock = freshMock()
    await expectApiError(mock.gateway.auth.me(), 401)

    await expect(mock.gateway.setup.chooseAuthMode('local')).resolves.toBeUndefined()
  })

  it('rejects an unknown mode with 422', async () => {
    const { gateway } = freshMock()

    await expectApiError(gateway.setup.chooseAuthMode('oidc' as 'ad'), 422)
  })
})

describe('setup.saveStorage precondition (AC-2)', () => {
  it('needs the auth mode first', async () => {
    const { gateway } = freshMock()

    await expectApiError(gateway.setup.saveStorage('/data/x'), 409, AUTH_MODE_FIRST)
  })

  it('needs no directory in local mode', async () => {
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('local')

    await gateway.setup.saveStorage('/data/neoine/files')

    expect(await gateway.setup.status()).toMatchObject({ storageDone: true })
  })

  it('still needs the directory in AD mode', async () => {
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('ad')

    await expectApiError(gateway.setup.saveStorage('/data/x'), 409, AD_FIRST)
  })
})

describe('setup.registerAdmin in local mode (AC-4)', () => {
  async function localReady() {
    const mock = freshMock()
    await mock.gateway.setup.chooseAuthMode('local')
    await mock.gateway.setup.saveStorage('/data/neoine/files')
    return mock
  }

  it('creates the admin with the profile and signs in', async () => {
    const { gateway } = await localReady()

    const me = await gateway.setup.registerAdmin('boss', PW, PROFILE)

    expect(me).toMatchObject({ loginId: 'boss', name: '보스', role: 'admin' })
    expect(await gateway.auth.me()).toEqual(me)
    expect(await gateway.setup.status()).toMatchObject({ adminDone: true })
    expect(await gateway.me.profile()).toMatchObject({ email: 'boss@corp.test', phone: '02-123-4567', authMode: 'local' })
  })

  it('keeps the password so that the admin can sign in again', async () => {
    const { gateway } = await localReady()
    await gateway.setup.registerAdmin('boss', PW, PROFILE)
    await gateway.auth.logout()

    await expectApiError(gateway.auth.login('boss', 'wrong-password'), 401, LOGIN_FAILED)
    const result = await gateway.auth.login('boss', PW)

    expect(result.me).toMatchObject({ loginId: 'boss', role: 'admin' })
    expect(result.directoryWarning).toBeNull()
  })

  it.each([
    ['name', { ...PROFILE, name: '  ' }, '이름을 입력하세요.'],
    ['email', { ...PROFILE, email: 'not-an-email' }, '이메일 형식이 올바르지 않습니다.'],
    ['phone', { ...PROFILE, phone: '12' }, '전화번호 형식이 올바르지 않습니다.'],
  ])('rejects an invalid %s with 422 and keeps the setup open', async (_field, profile, message) => {
    const { gateway } = await localReady()

    await expectApiError(gateway.setup.registerAdmin('boss', PW, profile), 422, message)

    expect((await gateway.setup.status()).adminDone).toBe(false)
  })

  it.each([
    ['short7!', '비밀번호는 8자 이상이어야 합니다.'],
    ['boss', '비밀번호는 8자 이상이어야 합니다.'],
    ['Boss.Admin1', '비밀번호는 아이디와 같을 수 없습니다.'],
  ])('rejects the password %s with 422', async (password, message) => {
    const { gateway } = await localReady()
    const loginId = password === 'Boss.Admin1' ? 'boss.admin1' : 'boss'

    await expectApiError(gateway.setup.registerAdmin(loginId, password, PROFILE), 422, message)

    expect((await gateway.setup.status()).adminDone).toBe(false)
  })

  it.each(['dev-admin', 'dev-sales', 'dev-user'])('rejects the reserved id %s with 422 in AD mode too', async (loginId) => {
    const { gateway } = freshMock()
    await gateway.setup.saveDirectory(DIRECTORY_INPUT)
    await gateway.setup.saveStorage('/data/files')

    await expectApiError(gateway.setup.registerAdmin(loginId, PW, undefined), 422, /개발 로그인 전용 아이디/)
    expect((await gateway.setup.status()).adminDone).toBe(false)
  })

  it.each(['dev-admin', 'dev-sales', 'dev-user'])('rejects the reserved id %s with 422', async (loginId) => {
    const { gateway } = await localReady()

    await expectApiError(gateway.setup.registerAdmin(loginId, PW, PROFILE), 422, /개발 로그인 전용 아이디/)
  })

  it('does not promote an existing active user (unlike the AD flow): the id is taken', async () => {
    const { gateway } = await localReady()

    await expectApiError(gateway.setup.registerAdmin('kim', PW, PROFILE), 409, '이미 사용 중인 아이디입니다.')
  })

  it('needs the storage step first', async () => {
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('local')

    await expectApiError(gateway.setup.registerAdmin('boss', PW, PROFILE), 409, '파일 저장 위치를 먼저 설정하세요.')
  })

  it('is refused once the admin exists', async () => {
    const { gateway } = await localReady()
    await gateway.setup.registerAdmin('boss', PW, PROFILE)

    await expectApiError(gateway.setup.registerAdmin('boss2', PW, PROFILE), 409)
  })

  it('rejects profile fields in AD mode with 422', async () => {
    const { gateway } = freshMock()
    await gateway.setup.saveDirectory(DIRECTORY_INPUT)
    await gateway.setup.saveStorage('/data/x')

    await expectApiError(gateway.setup.registerAdmin('boss', 'pw', PROFILE), 422)
    expect((await gateway.setup.status()).adminDone).toBe(false)
  })
})

describe('auth.login in local mode (AC-5)', () => {
  it('checks the password of a seeded user once the system is local', async () => {
    const { gateway, control } = await mockAs(null)
    control.setAuthMode('local')

    await expectApiError(gateway.auth.login('kim', 'wrong-password'), 401, LOGIN_FAILED)
    const ok = await gateway.auth.login('kim', SEED_PASSWORD)

    expect(ok.me).toMatchObject({ loginId: 'kim', role: 'sales' })
    expect(ok.directoryWarning).toBeNull()
  })

  it('fails alike for an unknown id', async () => {
    const { gateway, control } = await mockAs(null)
    control.setAuthMode('local')

    await expectApiError(gateway.auth.login('ghost', SEED_PASSWORD), 401, LOGIN_FAILED)
  })

  it('still accepts any password in AD mode (the directory decides on the server)', async () => {
    const { gateway } = await mockAs(null)

    await expect(gateway.auth.login('kim', 'anything')).resolves.toMatchObject({ me: { loginId: 'kim' } })
  })
})

/** 저장소에 예약 아이디 행이 남아 있어도(옛 데이터) 로그인은 서버처럼 401이다. */
async function mockWithUsers(...loginIds: string[]) {
  const mock = await mockAs(null)
  mock.setSeed((clock) => {
    const data = emptyBusinessSeed(clock)
    const template = data.users[0]!
    loginIds.forEach((loginId, i) => {
      data.users.push({ ...template, id: 9000 + i, loginId, role: 'sales', status: 'active' })
    })
    return data
  })
  return mock
}

describe('auth.login with the reserved dev ids', () => {
  it.each([
    ['ad', 'dev-admin'],
    ['ad', 'dev-sales'],
    ['ad', 'dev-user'],
    ['local', 'dev-admin'],
    ['local', 'dev-user'],
  ] as const)('rejects %s mode %s with 401 and the common message', async (mode, loginId) => {
    const { gateway, control } = await mockWithUsers(loginId)
    control.setAuthMode(mode)

    await expectApiError(gateway.auth.login(loginId, SEED_PASSWORD), 401, LOGIN_FAILED)
  })

  it.each(['ad', 'local'] as const)('lets another dev- id sign in in %s mode', async (mode) => {
    const { gateway, control } = await mockWithUsers('dev-ops')
    control.setAuthMode(mode)

    await expect(gateway.auth.login('dev-ops', SEED_PASSWORD)).resolves.toMatchObject({ me: { loginId: 'dev-ops' } })
  })
})

describe('control.setAuthMode', () => {
  it('switches a configured system to the other mode without touching the setup flags', async () => {
    const { gateway, control } = await mockAs('root')

    control.setAuthMode('local')

    expect(await gateway.setup.status()).toEqual({ authMode: 'local', directoryDone: true, storageDone: true, adminDone: true })
    expect(await gateway.auth.config()).toMatchObject({ authMode: 'local', needsSetup: false })
  })

  it('is undone by resetData', async () => {
    const { gateway, control } = await mockAs('root')
    control.setAuthMode('local')

    control.resetData()

    expect((await gateway.setup.status()).authMode).toBe('ad')
  })
})
