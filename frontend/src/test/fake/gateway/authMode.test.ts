import { describe, expect, it } from 'vitest'
import { DIRECTORY_INPUT } from '../../directoryFixtures'
import { emptyBusinessSeed } from '../seed'
import { SEED_PASSWORD } from '../seed/users'
import { expectApiError, mockAs, newMock } from '../testing'

/** 서버와 같은 문구·판정 순서를 지키는 Fake: 인증 방식 선택과 local 최초 설정·로그인 (계획). */
const AUTH_MODE_FIRST = '먼저 인증 방식을 고르세요.'
const AD_FIRST = '먼저 AD 서버를 등록하세요'
const CLOSED = '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다'
const LOGIN_FAILED = '아이디 또는 비밀번호가 올바르지 않습니다'
const PROFILE = { name: '보스', email: 'boss@corp.test', phone: '02-123-4567' }
const PW = 'Passw0rd-ok'

/** 최초 설정이 처음 상태인 mock. */
function freshMock() {
  const mock = newMock()
  mock.control.restartSetup()
  return mock
}

describe('setup.chooseAuthMode', () => {
  // local 방식을 고르면 AD 단계 없이 저장 위치 단계가 다음이 된다
  it('records local mode: no directory step is needed and the storage step is next', async () => {
    // given: 최초 설정이 처음 상태다
    const { gateway } = freshMock()

    // when: 인증 방식 local을 고른다
    const result = await gateway.setup.chooseAuthMode('local')

    // then: 상태는 local, AD 단계는 끝남, 저장 위치 단계가 남고 설정 필요로 표시된다
    expect(result).toBeUndefined()

    expect(await gateway.setup.status()).toEqual({ authMode: 'local', directoryDone: true, storageDone: false, adminDone: false })
    expect(await gateway.auth.config()).toMatchObject({ authMode: 'local', needsSetup: true })
  })

  // AD 방식을 고르면 방식만 기록되고 AD 서버 단계가 남는다
  it('records the AD mode but still needs the AD server', async () => {
    // given: 최초 설정이 처음 상태다
    const { gateway } = freshMock()

    await gateway.setup.chooseAuthMode('ad')

    // when: 인증 방식 ad를 고른다
    const actual = await gateway.setup.status()

    // then: 상태는 ad이고 AD 서버·저장 위치·관리자 단계가 모두 남는다
    expect(actual).toEqual({ authMode: 'ad', directoryDone: false, storageDone: false, adminDone: false })
  })

  // 첫 관리자가 생기기 전에는 방식을 다시 고를 수 있다
  it('can be chosen again until the first admin exists', async () => {
    // given: local을 이미 골랐다
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('local')

    await gateway.setup.chooseAuthMode('ad')

    // when: ad를 다시 고른다
    const actual = await gateway.setup.status()

    // then: 방식이 ad로 바뀌고 AD 단계가 다시 필요하다
    expect(actual).toMatchObject({ authMode: 'ad', directoryDone: false })
  })

  // local을 고른 뒤 AD 서버를 저장하면 방식이 ad로 바뀐다
  it('switches to the AD mode when the directory is saved after choosing local', async () => {
    // given: local을 골랐다
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('local')

    await gateway.setup.saveDirectory({ ...DIRECTORY_INPUT, ...await gateway.setup.testDirectory(DIRECTORY_INPUT) })

    // when: AD 서버를 저장한다
    const actual = await gateway.setup.status()

    // then: 방식은 ad이고 AD 단계가 끝난 상태다
    expect(actual).toMatchObject({ authMode: 'ad', directoryDone: true })
  })

  // 관리자가 생긴 뒤에는 두 방식 모두 409로 거절된다
  it('is refused with 409 once the first admin exists, for both modes', async () => {
    // given: 관리자가 이미 있는 mock이다
    const { gateway } = newMock()

    // when·then: local과 ad를 차례로 고른다 → 둘 다 409 문구이고 방식은 ad 그대로다
    await expectApiError(gateway.setup.chooseAuthMode('local'), 409, CLOSED)
    await expectApiError(gateway.setup.chooseAuthMode('ad'), 409, CLOSED)
    expect((await gateway.setup.status()).authMode).toBe('ad')
  })

  // 방식 선택은 세션 없이도 된다
  it('is public: it works without a session', async () => {
    // given: 최초 설정 처음 상태이고 세션이 없다
    const mock = freshMock()
    await expectApiError(mock.gateway.auth.me(), 401)

    // when: local을 고른다
    const result = await mock.gateway.setup.chooseAuthMode('local')
    // then: 오류 없이 끝난다
    expect(result).toBeUndefined()
  })

  // 알 수 없는 방식은 422로 거절된다
  it('rejects an unknown mode with 422', async () => {
    // given: 최초 설정이 처음 상태다
    const { gateway } = freshMock()

    // when·then: oidc 같은 알 수 없는 방식을 보낸다 → 422 오류다
    await expectApiError(gateway.setup.chooseAuthMode('oidc' as 'ad'), 422)
  })
})

describe('setup.saveStorage precondition', () => {
  // 방식을 고르기 전 저장 위치 저장은 방식 먼저 고르라는 409다
  it('needs the auth mode first', async () => {
    // given: 방식 미선택 상태다
    const { gateway } = freshMock()

    // when·then: 저장 위치를 저장한다 → 409 문구로 방식 선택을 요구한다
    await expectApiError(gateway.setup.saveStorage('/data/x'), 409, AUTH_MODE_FIRST)
  })

  // local 방식은 AD 서버 없이 저장 위치를 저장할 수 있다
  it('needs no directory in local mode', async () => {
    // given: local을 골랐다
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('local')

    await gateway.setup.saveStorage('/data/neoine/files')

    // when: 저장 위치를 저장한다
    const actual = await gateway.setup.status()

    // then: 저장 위치 단계가 끝남으로 바뀐다
    expect(actual).toMatchObject({ storageDone: true })
  })

  // AD 방식은 AD 서버를 먼저 등록하라는 409다
  it('still needs the directory in AD mode', async () => {
    // given: ad를 골랐고 AD 서버는 아직 없다
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('ad')

    // when·then: 저장 위치를 저장한다 → 409 문구로 AD 서버 등록을 요구한다
    await expectApiError(gateway.setup.saveStorage('/data/x'), 409, AD_FIRST)
  })
})

describe('setup.registerAdmin in local mode', () => {
  async function localReady() {
    const mock = freshMock()
    await mock.gateway.setup.chooseAuthMode('local')
    await mock.gateway.setup.saveStorage('/data/neoine/files')
    return mock
  }

  // local 최초 관리자를 프로필과 함께 만들고 로그인된다
  it('creates the admin with the profile and signs in', async () => {
    // given: local 방식과 저장 위치가 준비됐다
    const { gateway } = await localReady()

    // when: 아이디·비밀번호·프로필로 관리자를 등록한다
    const me = await gateway.setup.registerAdmin('boss', PW, PROFILE)

    // then: 관리자 역할의 본인이 로그인되고 프로필이 저장되며 관리자 단계가 끝난다
    expect(me).toMatchObject({ loginId: 'boss', name: '보스', role: 'admin' })
    expect(await gateway.auth.me()).toEqual(me)
    expect(await gateway.setup.status()).toMatchObject({ adminDone: true })
    expect(await gateway.me.profile()).toMatchObject({ email: 'boss@corp.test', phone: '02-123-4567', authMode: 'local' })
  })

  // 등록한 비밀번호로 다시 로그인할 수 있다
  it('keeps the password so that the admin can sign in again', async () => {
    // given: local 관리자를 등록하고 로그아웃했다
    const { gateway } = await localReady()
    await gateway.setup.registerAdmin('boss', PW, PROFILE)
    await gateway.auth.logout()

    // when·then: 틀린 비밀번호로 로그인한다 → 401이다
    await expectApiError(gateway.auth.login('boss', 'wrong-password'), 401, LOGIN_FAILED)
    // when: 맞는 비밀번호로 로그인한다
    const result = await gateway.auth.login('boss', PW)
    // then: 로그인되고 경고는 없다
    expect(result.me).toMatchObject({ loginId: 'boss', role: 'admin' })
    expect(result.directoryWarning).toBeNull()
  })

  // local 관리자 등록의 잘못된 프로필 칸은 422이고 설정이 열려 있다
  it.each([
    ['name', { ...PROFILE, name: '  ' }, '이름은(는) 비어 있을 수 없습니다'],
    ['email', { ...PROFILE, email: 'not-an-email' }, '이메일 형식이 올바르지 않습니다.'],
    ['phone', { ...PROFILE, phone: '12' }, '전화번호 형식이 올바르지 않습니다.'],
  ])('rejects an invalid %s with 422 and keeps the setup open', async (_field, profile, message) => {
    // given: local 방식과 저장 위치가 준비됐다
    const { gateway } = await localReady()

    // when·then: 이름·이메일·전화 중 하나가 틀린 프로필로 등록한다 → 422 문구이고 관리자 단계는 끝나지 않는다
    await expectApiError(gateway.setup.registerAdmin('boss', PW, profile), 422, message)

    expect((await gateway.setup.status()).adminDone).toBe(false)
  })

  // local 관리자 등록의 약한 비밀번호는 422이고 설정이 열려 있다
  it.each([
    ['short7!', '비밀번호는 8자 이상이어야 합니다'],
    ['boss', '비밀번호는 8자 이상이어야 합니다'],
    ['Boss.Admin1', '비밀번호는 아이디와 같을 수 없습니다'],
  ])('rejects the password %s with 422', async (password, message) => {
    // given: local 방식과 저장 위치가 준비됐다
    const { gateway } = await localReady()

    // when: 8자 미만이거나 아이디와 같은 비밀번호로 등록한다
    const loginId = password === 'Boss.Admin1' ? 'boss.admin1' : 'boss'

    // then: 422 문구이고 관리자 단계는 끝나지 않는다
    await expectApiError(gateway.setup.registerAdmin(loginId, password, PROFILE), 422, message)

    expect((await gateway.setup.status()).adminDone).toBe(false)
  })

  // AD 방식에서도 예약 아이디는 422다
  it.each(['dev-admin', 'dev-sales', 'dev-user'])('rejects the reserved id %s with 422 in AD mode too', async (loginId) => {
    // given: AD 서버와 저장 위치가 등록됐다
    const { gateway } = freshMock()
    await gateway.setup.saveDirectory({ ...DIRECTORY_INPUT, ...await gateway.setup.testDirectory(DIRECTORY_INPUT) })

    // when: 예약 아이디로 관리자를 등록한다
    await gateway.setup.saveStorage('/data/files')

    // then: 422이고 관리자 단계는 끝나지 않는다
    await expectApiError(gateway.setup.registerAdmin(loginId, PW, undefined), 422, /개발 로그인 전용 아이디/)
    expect((await gateway.setup.status()).adminDone).toBe(false)
  })

  // local 방식에서 예약 아이디는 422다
  it.each(['dev-admin', 'dev-sales', 'dev-user'])('rejects the reserved id %s with 422', async (loginId) => {
    // given: local 방식과 저장 위치가 준비됐다
    const { gateway } = await localReady()

    // when·then: 예약 아이디로 관리자를 등록한다 → 422 문구다
    await expectApiError(gateway.setup.registerAdmin(loginId, PW, PROFILE), 422, /개발 로그인 전용 아이디/)
  })

  // local 방식은 기존 재직 사용자를 관리자로 올리지 않고 아이디 중복 409다
  it('does not promote an existing active user (unlike the AD flow): the id is taken', async () => {
    // given: local 방식과 저장 위치가 준비됐고 kim이 이미 있다
    const { gateway } = await localReady()

    // when·then: kim으로 관리자를 등록한다 → 409 중복 문구다
    await expectApiError(gateway.setup.registerAdmin('kim', PW, PROFILE), 409, '이미 존재하는 사용자입니다: kim')
  })

  // 저장 위치 단계 전에 관리자를 등록하면 409다
  it('needs the storage step first', async () => {
    // given: local을 골랐고 저장 위치는 아직 없다
    const { gateway } = freshMock()
    await gateway.setup.chooseAuthMode('local')

    // when·then: 관리자를 등록한다 → 409 문구로 저장 위치를 먼저 설정하라고 한다
    await expectApiError(gateway.setup.registerAdmin('boss', PW, PROFILE), 409, '파일 저장 위치를 먼저 설정하세요.')
  })

  // 관리자가 이미 있으면 관리자 등록은 409다
  it('is refused once the admin exists', async () => {
    // given: 관리자를 등록했다
    const { gateway } = await localReady()
    await gateway.setup.registerAdmin('boss', PW, PROFILE)

    // when·then: 다른 아이디로 관리자를 또 등록한다 → 409 오류다
    await expectApiError(gateway.setup.registerAdmin('boss2', PW, PROFILE), 409)
  })

  // AD 방식에서 프로필을 보내면 422다
  it('rejects profile fields in AD mode with 422', async () => {
    // given: AD 서버와 저장 위치가 등록됐다
    const { gateway } = freshMock()
    await gateway.setup.saveDirectory({ ...DIRECTORY_INPUT, ...await gateway.setup.testDirectory(DIRECTORY_INPUT) })

    // when: 프로필 칸을 담아 관리자를 등록한다
    await gateway.setup.saveStorage('/data/x')

    // then: 422이고 관리자 단계는 끝나지 않는다
    await expectApiError(gateway.setup.registerAdmin('boss', 'pw', PROFILE), 422)
    expect((await gateway.setup.status()).adminDone).toBe(false)
  })
})

describe('auth.login in local mode', () => {
  // local 방식 시스템은 시드 사용자의 비밀번호를 확인한다
  it('checks the password of a seeded user once the system is local', async () => {
    // given: local 방식이고 로그인하지 않았다
    const { gateway, control } = await mockAs(null)

    control.setAuthMode('local')

    // when·then: 틀린 비밀번호로 kim이 로그인한다 → 401이다
    await expectApiError(gateway.auth.login('kim', 'wrong-password'), 401, LOGIN_FAILED)
    // when: 맞는 비밀번호로 kim이 로그인한다
    const ok = await gateway.auth.login('kim', SEED_PASSWORD)
    // then: sales kim이 로그인되고 경고는 없다
    expect(ok.me).toMatchObject({ loginId: 'kim', role: 'sales' })
    expect(ok.directoryWarning).toBeNull()
  })

  // local 방식에서 없는 아이디도 같은 401이다
  it('fails alike for an unknown id', async () => {
    // given: local 방식이다
    const { gateway, control } = await mockAs(null)
    control.setAuthMode('local')

    // when·then: 없는 아이디로 로그인한다 → 공통 실패 문구의 401이다
    await expectApiError(gateway.auth.login('ghost', SEED_PASSWORD), 401, LOGIN_FAILED)
  })

  // AD 방식에서도 저장된 비밀번호를 확인한다
  it('checks the stored password in AD mode too (the directory decides on the server)', async () => {
    // given: AD 방식(기본)이다
    const { gateway } = await mockAs(null)

    // when·then: 틀린 비밀번호와 맞는 비밀번호로 로그인한다 → 틀리면 401, 맞으면 로그인된다
    await expectApiError(gateway.auth.login('kim', 'anything'), 401, LOGIN_FAILED)
    await expect(gateway.auth.login('kim', SEED_PASSWORD)).resolves.toMatchObject({ me: { loginId: 'kim' } })
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
  // 저장소에 예약 아이디 행이 남아 있어도 로그인은 401이다
  it.each([
    ['ad', 'dev-admin'],
    ['ad', 'dev-sales'],
    ['ad', 'dev-user'],
    ['local', 'dev-admin'],
    ['local', 'dev-user'],
  ] as const)('rejects %s mode %s with 401 and the common message', async (mode, loginId) => {
    // given: 예약 아이디 행이 저장소에 있고 방식은 ad 또는 local이다
    const { gateway, control } = await mockWithUsers(loginId)
    control.setAuthMode(mode)

    // when·then: 그 아이디로 로그인한다 → 공통 실패 문구의 401이다
    await expectApiError(gateway.auth.login(loginId, SEED_PASSWORD), 401, LOGIN_FAILED)
  })

  // 예약 3개가 아닌 dev- 아이디는 일반 사용자로 로그인된다
  it.each(['ad', 'local'] as const)('lets another dev- id sign in in %s mode', async (mode) => {
    // given: dev-ops 행이 저장소에 있다
    const { gateway, control } = await mockWithUsers('dev-ops')
    control.setAuthMode(mode)

    // when: ad·local 방식에서 로그인한다
    const result = await gateway.auth.login('dev-ops', SEED_PASSWORD)
    // then: 로그인된다
    expect(result).toMatchObject({ me: { loginId: 'dev-ops' } })
  })
})

describe('control.setAuthMode', () => {
  // 방식 전환 제어는 설정 단계 표시를 건드리지 않는다
  it('switches a configured system to the other mode without touching the setup flags', async () => {
    // given: 최초 설정이 모두 끝난 mock이다
    const { gateway, control } = await mockAs('root')

    control.setAuthMode('local')

    // when: 제어 도구로 local로 전환한다
    const actual1 = await gateway.setup.status()
    const actual2 = await gateway.auth.config()

    // then: 방식만 local이 되고 세 단계는 끝남 그대로이며 설정은 필요하지 않다
    expect(actual1).toEqual({ authMode: 'local', directoryDone: true, storageDone: true, adminDone: true })
    expect(actual2).toMatchObject({ authMode: 'local', needsSetup: false })
  })

  // 데이터 초기화는 방식 전환을 되돌린다
  it('is undone by resetData', async () => {
    // given: local로 전환한 mock이다
    const { gateway, control } = await mockAs('root')
    control.setAuthMode('local')

    control.resetData()

    // when: 데이터를 초기화한다
    const actual = (await gateway.setup.status()).authMode

    // then: 방식이 ad로 돌아온다
    expect(actual).toBe('ad')
  })
})
