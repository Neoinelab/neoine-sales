import { describe, expect, it } from 'vitest'
import { DIRECTORY_INPUT } from '../../directoryFixtures'
import type { SeedData } from '../store'
import { buildSampleSeed } from '../../fixtures/sampleSeed'
import { expectApiError, mockAs, newMock } from '../testing'

const DIRECTORY = DIRECTORY_INPUT

const ADMIN_EXISTS = '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다'

/** 최초 설정 진행 상태를 직접 정한 mock(관리자가 이미 있는 DB에 저장 위치만 없는 경우 등). */
function mockWithSetup(setup: Omit<SeedData['setup'], 'authMode'>) {
  return newMock({ seed: (clock) => ({ ...buildSampleSeed(clock), setup: { ...setup, authMode: 'ad' as const } }) })
}

describe('setup.testStorage / settings.testStorage (쓰기 테스트)', () => {
  // 최초 설정 쓰기 테스트는 로그인 없이 되고 저장 없이 검증만 한다
  it('works before login and validates like saveStorage without saving', async () => {
    // given: 최초 설정 처음 상태이고 세션이 없다
    const mock = newMock()
    mock.control.restartSetup()
    // when: 정상·상대·읽기 전용 경로로 쓰기 테스트를 한다
    const { setup } = mock.gateway

    // then: 정상은 통과, 상대는 절대 경로 422, 읽기 전용은 쓸 수 없음 422이며 설정 상태는 그대로다
    await expect(setup.testStorage('/data/neoine/files')).resolves.toBeUndefined()
    await expectApiError(setup.testStorage('relative/path'), 422, '절대 경로를 입력하세요.')
    await expectApiError(setup.testStorage('/readonly/files'), 422, '해당 위치에 쓸 수 없습니다.')
    expect(await setup.status()).toEqual({ directoryDone: false, storageDone: false, adminDone: false, authMode: null })
  })

  // 쓰기 테스트는 AD 서버 단계가 끝나지 않아도 된다
  it('does not require the AD server step to be done first', async () => {
    // given: 최초 설정 처음 상태다
    const mock = newMock()
    // when: 쓰기 테스트를 한다
    mock.control.restartSetup()
    // then: 오류 없이 끝난다
    await expect(mock.gateway.setup.testStorage('/data/x')).resolves.toBeUndefined()
  })

  // 서버의 최초 설정 쓰기 테스트도 저장소 장애 503을 내지 않는다(SU-R8)
  it('keeps the setup write test free of the 503 simulation', async () => {
    // given: 저장소 장애 시뮬레이션을 켰다
    const mock = newMock()
    mock.control.restartSetup()
    // when: 최초 설정 쓰기 테스트를 정상 경로로 한다
    mock.control.setStorageFailure(true)
    // then: 오류 없이 끝난다
    await expect(mock.gateway.setup.testStorage('/data/x')).resolves.toBeUndefined()
  })

  // 서버의 관리자 쓰기 테스트는 저장소 장애 503을 내지 않는다(IN-R26): 503 시뮬레이션은 첨부·계약·최초 설정용이다.
  // 관리자 설정 화면의 쓰기 테스트는 503 시뮬레이션의 영향을 받지 않는다
  it('keeps the admin settings write test free of the 503 simulation', async () => {
    // given: admin이고 저장소 장애 시뮬레이션을 켰다
    const mock = await mockAs('root')
    // when: 설정 화면의 쓰기 테스트를 한다
    mock.control.setStorageFailure(true)
    // then: 오류 없이 끝난다
    await expect(mock.gateway.settings.testStorage('/data/x')).resolves.toBeUndefined()
  })
})

describe('최초 설정 저장 위치 단계 (R-24)', () => {
  // 관리자가 있으면 저장·테스트는 경로를 보기 전에 409다
  it('refuses saving and testing with 409 once the admin exists, before looking at the path', async () => {
    // given: 관리자가 이미 있다
    const mock = newMock()

    // when·then: 정상·상대 경로로 저장과 테스트를 한다 → 모두 관리자 존재 409다
    await expectApiError(mock.gateway.setup.saveStorage('/data/x'), 409, ADMIN_EXISTS)
    await expectApiError(mock.gateway.setup.saveStorage('relative'), 409, ADMIN_EXISTS)
    await expectApiError(mock.gateway.setup.testStorage('/data/x'), 409, ADMIN_EXISTS)
    await expectApiError(mock.gateway.setup.testStorage('relative'), 409, ADMIN_EXISTS)
  })

  // 관리자 존재 409가 AD 우선 409보다 먼저 판정된다
  it('judges the admin-exists 409 before the AD-first 409', async () => {
    // given: 관리자는 있고 AD·저장 위치는 없다
    const mock = mockWithSetup({ directoryDone: false, storageDone: false, adminDone: true })

    // when·then: 저장 위치를 저장한다 → 관리자 존재 문구의 409다
    await expectApiError(mock.gateway.setup.saveStorage('/data/x'), 409, ADMIN_EXISTS)
  })

  // 방식을 고르지 않았으면 경로 규칙보다 먼저 방식 선택 409다
  it('asks for the auth mode first with the server message, before the path rules', async () => {
    // given: 방식 미선택 처음 상태다
    const mock = newMock()
    // when: 정상·상대 경로를 저장한다
    mock.control.restartSetup()
    // then: 모두 방식 먼저 고르라는 409이고 단계 상태는 그대로다
    await expectApiError(mock.gateway.setup.saveStorage('/data/x'), 409, '먼저 인증 방식을 고르세요.')
    await expectApiError(mock.gateway.setup.saveStorage('relative'), 409, '먼저 인증 방식을 고르세요.')
    expect(await mock.gateway.setup.status()).toEqual({ directoryDone: false, storageDone: false, adminDone: false, authMode: null })
  })

  // ad를 골랐으면 경로 규칙보다 먼저 AD 서버 409다
  it('asks for the AD server first once the AD mode is chosen, before the path rules', async () => {
    // given: ad를 골랐고 AD 서버는 없다
    const mock = newMock()
    mock.control.restartSetup()
    // when: 정상·상대 경로를 저장한다
    await mock.gateway.setup.chooseAuthMode('ad')
    // then: 모두 AD 서버 먼저 등록하라는 409이고 상태는 그대로다
    await expectApiError(mock.gateway.setup.saveStorage('/data/x'), 409, '먼저 AD 서버를 등록하세요')
    await expectApiError(mock.gateway.setup.saveStorage('relative'), 409, '먼저 AD 서버를 등록하세요')
    expect(await mock.gateway.setup.status()).toEqual({ directoryDone: false, storageDone: false, adminDone: false, authMode: 'ad' })
  })

  // AD 서버 뒤 저장 위치를 저장하고 관리자 전까지 다시 저장해 덮어쓴다
  it('saves the location after the AD server step and lets it be saved again until the admin exists', async () => {
    // given: AD 서버를 저장했다
    const mock = newMock()
    mock.control.restartSetup()
    const { setup } = mock.gateway
    await setup.saveDirectory({ ...DIRECTORY, ...await mock.gateway.setup.testDirectory(DIRECTORY) })
    await setup.saveStorage('/data/first')
    // when: 저장 위치를 두 번 저장하고 관리자를 등록한다
    await setup.saveStorage('/data/second')
    // then: 단계 상태가 맞고 저장된 경로는 두 번째 값이다
    expect(await setup.status()).toEqual({ directoryDone: true, storageDone: true, adminDone: false, authMode: 'ad' })
    await setup.registerAdmin('newadmin', 'pw')
    const { settings } = mock.gateway
    expect((await settings.getStorage())?.path).toBe('/data/second')
  })

  // 거절된 경로는 아무것도 저장하지 않는다
  it('keeps nothing saved when the path is refused', async () => {
    // given: AD 서버를 저장했다
    const mock = newMock()
    mock.control.restartSetup()
    // when: 읽기 전용 경로를 저장한다
    await mock.gateway.setup.saveDirectory({ ...DIRECTORY, ...await mock.gateway.setup.testDirectory(DIRECTORY) })
    // then: 422이고 저장 위치 단계는 끝나지 않는다
    await expectApiError(mock.gateway.setup.saveStorage('/readonly/x'), 422, '해당 위치에 쓸 수 없습니다.')
    expect((await mock.gateway.setup.status()).storageDone).toBe(false)
  })

  // 저장 위치 전에는 관리자 등록이 409다
  it('refuses the admin registration with 409 until the location is saved', async () => {
    // given: AD 서버만 저장했다
    const mock = newMock()
    mock.control.restartSetup()
    // when: 관리자를 등록한다
    await mock.gateway.setup.saveDirectory({ ...DIRECTORY, ...await mock.gateway.setup.testDirectory(DIRECTORY) })
    // then: 409 문구로 저장 위치를 먼저 설정하라고 한다
    await expectApiError(mock.gateway.setup.registerAdmin('root', 'pw'), 409, '파일 저장 위치를 먼저 설정하세요.')
  })
})

describe('auth.config.needsSetup 는 저장 단계를 포함한다', () => {
  // 모든 단계가 끝나면 설정 필요가 아니다
  it('is false when every step is done', async () => {
    // given: 모든 단계가 끝난 mock이다
    const mock = newMock()
    // when: 로그인 설정을 읽는다
    const config = await mock.gateway.auth.config()
    // then: 설정 필요가 false다
    expect(config.needsSetup).toBe(false)
  })

  // 저장 위치 단계만 비면 설정 필요다
  it('is true when only the storage step is missing', async () => {
    // given: AD·관리자는 끝났고 저장 위치만 없다
    const mock = mockWithSetup({ directoryDone: true, storageDone: false, adminDone: true })
    // when: 로그인 설정을 읽는다
    const config = await mock.gateway.auth.config()
    // then: 설정 필요가 true다
    expect(config.needsSetup).toBe(true)
  })

  // AD 단계만 비면 설정 필요다
  it('is true when only the AD step is missing', async () => {
    // given: 저장 위치·관리자는 끝났고 AD만 없다
    const mock = mockWithSetup({ directoryDone: false, storageDone: true, adminDone: true })
    // when: 로그인 설정을 읽는다
    const config = await mock.gateway.auth.config()
    // then: 설정 필요가 true다
    expect(config.needsSetup).toBe(true)
  })

  // 관리자 단계만 비면 설정 필요다
  it('is true when only the admin step is missing', async () => {
    // given: AD·저장 위치는 끝났고 관리자만 없다
    const mock = mockWithSetup({ directoryDone: true, storageDone: true, adminDone: false })
    // when: 로그인 설정을 읽는다
    const config = await mock.gateway.auth.config()
    // then: 설정 필요가 true다
    expect(config.needsSetup).toBe(true)
  })

  // 처음 상태에서는 세 번째 단계가 끝나야 설정 필요가 사라진다
  it('turns false only after the third step of a fresh setup', async () => {
    // given: 최초 설정 처음 상태다
    const mock = newMock()
    mock.control.restartSetup()
    // when: AD, 저장 위치, 관리자를 차례로 저장한다
    const { setup, auth } = mock.gateway
    // then: 마지막 단계 뒤에만 설정 필요가 false다
    expect((await auth.config()).needsSetup).toBe(true)
    await setup.saveDirectory({ ...DIRECTORY, ...await mock.gateway.setup.testDirectory(DIRECTORY) })
    expect((await auth.config()).needsSetup).toBe(true)
    await setup.saveStorage('/data/x')
    expect((await auth.config()).needsSetup).toBe(true)
    await setup.registerAdmin('newadmin', 'pw')
    expect((await auth.config()).needsSetup).toBe(false)
  })
})

describe('저장 경로 규칙 (R-23, 서버 StoragePath와 같은 경계)', () => {
  const NOT_ABSOLUTE = '절대 경로를 입력하세요.'
  const TOO_LONG = '저장 경로는 1024자 이내로 입력하세요.'

  // 절대 경로가 아닌 값은 설정 화면의 저장·테스트에서 같은 422다
  it.each(['', '   ', 'relative/path', './files', '/a/../b', '/..', '/a/..', ' ../x'])('refuses %j as not absolute', async (path) => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: 빈 값·공백·상대·`..` 경로를 저장과 테스트한다 → 모두 절대 경로 입력 422다
    await expectApiError(gateway.settings.saveStorage(path), 422, NOT_ABSOLUTE)
    await expectApiError(gateway.settings.testStorage(path), 422, NOT_ABSOLUTE)
  })

  // 최초 설정 테스트도 같은 절대 경로 문구를 쓴다
  it.each(['', 'relative', '/x/../y'])('shows the same message through the first-time setup test for %j', async (path) => {
    // given: 최초 설정 처음 상태다
    const mock = newMock()
    // when: 빈 값·상대·`..` 경로를 테스트한다
    mock.control.restartSetup()
    // then: 절대 경로 입력 422다
    await expectApiError(mock.gateway.setup.testStorage(path), 422, NOT_ABSOLUTE)
  })

  // 정규화 뒤 1024자는 허용하고 1025자는 거절한다
  it('allows 1024 characters after normalising and refuses 1025', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when: 1024자와 1025자 경로를 테스트·저장한다
    const result = await gateway.settings.testStorage(`/${'a'.repeat(1023)}`)

    // then: 1024자는 통과, 1025자는 길이 422다
    expect(result).toBeUndefined()
    await expectApiError(gateway.settings.testStorage(`/${'a'.repeat(1024)}`), 422, TOO_LONG)
    await expectApiError(gateway.settings.saveStorage(`/${'a'.repeat(1024)}`), 422, TOO_LONG)
  })

  // 길이는 중복 슬래시·점·끝 슬래시를 정리한 뒤 잰다
  it('measures the length after dropping duplicate slashes, dots and the trailing slash', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when: 중복 슬래시가 수천 개인 경로를 테스트한다
    const result = await gateway.settings.testStorage(`/${'/'.repeat(2000)}${'a'.repeat(1000)}/./`)

    // then: 정리 뒤 길이가 한도 안이라 통과한다
    expect(result).toBeUndefined()
  })

  // 저장 경로는 공백·중복 슬래시·점·끝 슬래시를 정리해 저장한다
  it('saves the trimmed path with duplicate slashes, single dots and the trailing slash removed', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')
    // when: 정리가 필요한 경로를 저장한다
    const saved = await gateway.settings.saveStorage('  //data//./files/  ')
    // then: 정리된 경로가 응답과 조회에 같다
    expect(saved.path).toBe('/data/files')
    expect((await gateway.settings.getStorage())?.path).toBe('/data/files')
  })

  // NUL 문자가 든 경로는 422다
  it('refuses a NUL character', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: NUL이 든 경로를 저장한다 → NUL 금지 422다
    await expectApiError(gateway.settings.saveStorage('/data/\u0000x'), 422, '저장 경로에는 NUL 문자를 쓸 수 없습니다')
  })

  // /readonly 아래는 쓸 수 없는 위치로 시뮬레이션된다
  it('still simulates an unwritable location under /readonly', async () => {
    // given: admin이다
    const { gateway } = await mockAs('root')

    // when·then: /readonly/x를 저장한다 → 쓸 수 없음 422다
    await expectApiError(gateway.settings.saveStorage('/readonly/x'), 422, '해당 위치에 쓸 수 없습니다.')
  })
})
