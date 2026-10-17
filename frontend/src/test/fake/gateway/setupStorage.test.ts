import { describe, expect, it } from 'vitest'
import type { DirectorySettingsInput } from '../../../shared/model/types'
import type { SeedData } from '../store'
import { buildSampleSeed } from '../../fixtures/sampleSeed'
import { expectApiError, mockAs, newMock } from '../testing'

const DIRECTORY: DirectorySettingsInput = {
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

const ADMIN_EXISTS = '이미 관리자가 등록되어 최초 설정을 진행할 수 없습니다'

/** 최초 설정 진행 상태를 직접 정한 mock(관리자가 이미 있는 DB에 저장 위치만 없는 경우 등). */
function mockWithSetup(setup: SeedData['setup']) {
  return newMock({ seed: (clock) => ({ ...buildSampleSeed(clock), setup }) })
}

describe('setup.testStorage / settings.testStorage (쓰기 테스트)', () => {
  it('works before login and validates like saveStorage without saving', async () => {
    const mock = newMock()
    mock.control.restartSetup()
    const { setup } = mock.gateway

    await expect(setup.testStorage('/data/neoine/files')).resolves.toBeUndefined()
    await expectApiError(setup.testStorage('relative/path'), 422, '절대 경로를 입력하세요.')
    await expectApiError(setup.testStorage('/readonly/files'), 422, '해당 위치에 쓸 수 없습니다.')
    expect(await setup.status()).toEqual({ directoryDone: false, storageDone: false, adminDone: false })
  })

  it('does not require the AD server step to be done first', async () => {
    const mock = newMock()
    mock.control.restartSetup()
    await expect(mock.gateway.setup.testStorage('/data/x')).resolves.toBeUndefined()
  })

  it('fails with 503 and a readable message while the storage failure simulation is on', async () => {
    const mock = newMock()
    mock.control.restartSetup()
    mock.control.setStorageFailure(true)
    await expectApiError(mock.gateway.setup.testStorage('/data/x'), 503, /파일 저장 위치를 사용할 수 없습니다\./)
  })

  it('makes the admin settings test fail with 503 under the same simulation', async () => {
    const mock = await mockAs('root')
    mock.control.setStorageFailure(true)
    await expectApiError(mock.gateway.settings.testStorage('/data/x'), 503, /파일 저장 위치를 사용할 수 없습니다\./)
  })
})

describe('최초 설정 저장 위치 단계 (AC-02, AC-03, AC-20, R-24)', () => {
  it('refuses saving and testing with 409 once the admin exists, before looking at the path', async () => {
    const mock = newMock()
    await expectApiError(mock.gateway.setup.saveStorage('/data/x'), 409, ADMIN_EXISTS)
    await expectApiError(mock.gateway.setup.saveStorage('relative'), 409, ADMIN_EXISTS)
    await expectApiError(mock.gateway.setup.testStorage('/data/x'), 409, ADMIN_EXISTS)
    await expectApiError(mock.gateway.setup.testStorage('relative'), 409, ADMIN_EXISTS)
  })

  it('judges the admin-exists 409 before the AD-first 409', async () => {
    const mock = mockWithSetup({ directoryDone: false, storageDone: false, adminDone: true })
    await expectApiError(mock.gateway.setup.saveStorage('/data/x'), 409, ADMIN_EXISTS)
  })

  it('asks for the AD server first with the server message, before the path rules', async () => {
    const mock = newMock()
    mock.control.restartSetup()
    await expectApiError(mock.gateway.setup.saveStorage('/data/x'), 409, '먼저 AD 서버를 등록하세요')
    await expectApiError(mock.gateway.setup.saveStorage('relative'), 409, '먼저 AD 서버를 등록하세요')
    expect(await mock.gateway.setup.status()).toEqual({ directoryDone: false, storageDone: false, adminDone: false })
  })

  it('saves the location after the AD server step and lets it be saved again until the admin exists', async () => {
    const mock = newMock()
    mock.control.restartSetup()
    const { setup } = mock.gateway
    await setup.saveDirectory(DIRECTORY)
    await setup.saveStorage('/data/first')
    await setup.saveStorage('/data/second')
    expect(await setup.status()).toEqual({ directoryDone: true, storageDone: true, adminDone: false })
    await setup.registerAdmin('root', 'pw')
    const { settings } = mock.gateway
    expect((await settings.getStorage())?.path).toBe('/data/second')
  })

  it('keeps nothing saved when the path is refused', async () => {
    const mock = newMock()
    mock.control.restartSetup()
    await mock.gateway.setup.saveDirectory(DIRECTORY)
    await expectApiError(mock.gateway.setup.saveStorage('/readonly/x'), 422, '해당 위치에 쓸 수 없습니다.')
    expect((await mock.gateway.setup.status()).storageDone).toBe(false)
  })

  it('refuses the admin registration with 409 until the location is saved', async () => {
    const mock = newMock()
    mock.control.restartSetup()
    await mock.gateway.setup.saveDirectory(DIRECTORY)
    await expectApiError(mock.gateway.setup.registerAdmin('root', 'pw'), 409, '파일 저장 위치를 먼저 설정하세요.')
  })
})

describe('auth.config.needsSetup 는 저장 단계를 포함한다 (AC-01, AC-20)', () => {
  it('is false when every step is done', async () => {
    expect((await newMock().gateway.auth.config()).needsSetup).toBe(false)
  })

  it('is true when only the storage step is missing', async () => {
    const mock = mockWithSetup({ directoryDone: true, storageDone: false, adminDone: true })
    expect((await mock.gateway.auth.config()).needsSetup).toBe(true)
  })

  it('is true when only the AD step is missing', async () => {
    const mock = mockWithSetup({ directoryDone: false, storageDone: true, adminDone: true })
    expect((await mock.gateway.auth.config()).needsSetup).toBe(true)
  })

  it('is true when only the admin step is missing', async () => {
    const mock = mockWithSetup({ directoryDone: true, storageDone: true, adminDone: false })
    expect((await mock.gateway.auth.config()).needsSetup).toBe(true)
  })

  it('turns false only after the third step of a fresh setup', async () => {
    const mock = newMock()
    mock.control.restartSetup()
    const { setup, auth } = mock.gateway
    expect((await auth.config()).needsSetup).toBe(true)
    await setup.saveDirectory(DIRECTORY)
    expect((await auth.config()).needsSetup).toBe(true)
    await setup.saveStorage('/data/x')
    expect((await auth.config()).needsSetup).toBe(true)
    await setup.registerAdmin('root', 'pw')
    expect((await auth.config()).needsSetup).toBe(false)
  })
})

describe('저장 경로 규칙 (R-23, 서버 StoragePath와 같은 경계)', () => {
  const NOT_ABSOLUTE = '절대 경로를 입력하세요.'
  const TOO_LONG = '저장 경로는 1024자 이내로 입력하세요.'

  it.each(['', '   ', 'relative/path', './files', '/a/../b', '/..', '/a/..', ' ../x'])('refuses %j as not absolute', async (path) => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.settings.saveStorage(path), 422, NOT_ABSOLUTE)
    await expectApiError(gateway.settings.testStorage(path), 422, NOT_ABSOLUTE)
  })

  it.each(['', 'relative', '/x/../y'])('shows the same message through the first-time setup test for %j', async (path) => {
    const mock = newMock()
    mock.control.restartSetup()
    await expectApiError(mock.gateway.setup.testStorage(path), 422, NOT_ABSOLUTE)
  })

  it('allows 1024 characters after normalising and refuses 1025', async () => {
    const { gateway } = await mockAs('root')
    await expect(gateway.settings.testStorage(`/${'a'.repeat(1023)}`)).resolves.toBeUndefined()
    await expectApiError(gateway.settings.testStorage(`/${'a'.repeat(1024)}`), 422, TOO_LONG)
    await expectApiError(gateway.settings.saveStorage(`/${'a'.repeat(1024)}`), 422, TOO_LONG)
  })

  it('measures the length after dropping duplicate slashes, dots and the trailing slash', async () => {
    const { gateway } = await mockAs('root')
    await expect(gateway.settings.testStorage(`/${'/'.repeat(2000)}${'a'.repeat(1000)}/./`)).resolves.toBeUndefined()
  })

  it('saves the trimmed path with duplicate slashes, single dots and the trailing slash removed', async () => {
    const { gateway } = await mockAs('root')
    const saved = await gateway.settings.saveStorage('  //data//./files/  ')
    expect(saved.path).toBe('/data/files')
    expect((await gateway.settings.getStorage())?.path).toBe('/data/files')
  })

  it('refuses a NUL character', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.settings.saveStorage('/data/\u0000x'), 422, '저장 경로에는 NUL 문자를 쓸 수 없습니다')
  })

  it('still simulates an unwritable location under /readonly', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.settings.saveStorage('/readonly/x'), 422, '해당 위치에 쓸 수 없습니다.')
  })
})
