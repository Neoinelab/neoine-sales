import { describe, expect, it } from 'vitest'
import { SETUP_DIRECTORY_INPUT, TEST_PASSWORD } from '../../directoryFixtures'
import { SEED_PASSWORD } from '../seed/users'
import { expectApiError, newMock } from '../testing'

const LOGIN_ID_FORMAT = 'test_login_id: 로그인 아이디는 영문 소문자·숫자·점·밑줄·하이픈으로 64자 이하여야 합니다'

/** 최초 설정이 처음 상태인 mock. */
function freshMock() {
  const mock = newMock()
  mock.control.restartSetup()
  return mock
}

describe('setup.testDirectory / setup.saveDirectory (테스트 계정, SU-R6·SU-R20 모사)', () => {
  // 연결 테스트는 저장 없이 찾은 Base DN만 돌려준다
  it('tests without saving and answers the found base DN', async () => {
    // given: 최초 설정 처음 상태다
    const mock = freshMock()

    // when: 테스트 계정과 함께 연결 테스트를 한다
    const result = await mock.gateway.setup.testDirectory(SETUP_DIRECTORY_INPUT)

    // then: Base DN이 돌아오고 진행 상태는 그대로다
    expect(result).toEqual({ baseDn: 'dc=found,dc=test' })
    expect(await mock.gateway.setup.status()).toEqual({ directoryDone: false, storageDone: false, adminDone: false, authMode: null })
  })

  // 등록은 테스트 계정·비밀번호를 저장 결과에 담지 않는다
  it('registers the directory without storing the test account or its password', async () => {
    // given: AD 서버·저장 위치·첫 관리자까지 등록해 최초 설정을 마쳤다
    const mock = freshMock()
    await mock.gateway.setup.saveDirectory(SETUP_DIRECTORY_INPUT)
    await mock.gateway.setup.saveStorage('/data/neoine/files')
    await mock.gateway.setup.registerAdmin('newadmin', SEED_PASSWORD)

    // when: 로그인한 admin이 저장된 AD 설정을 읽는다
    const saved = await mock.gateway.settings.getDirectory()

    // then: 5칸과 Base DN만 있고 테스트 계정·비밀번호·바인드 키는 어디에도 없다
    expect(saved).toMatchObject({ host: 'dc1.corp.test', port: 636, security: 'ssl', baseDn: 'dc=corp,dc=test' })
    expect(JSON.stringify(saved)).not.toContain(TEST_PASSWORD)
    expect(JSON.stringify(saved)).not.toMatch(/test_?login|test_?password|bind/i)
  })

  // 테스트 계정 아이디는 앞뒤 공백을 지우고 소문자로 바꾼 값이 로그인 아이디 형식이면 된다
  it('accepts a test login id with surrounding spaces and upper case letters', async () => {
    // given: 최초 설정 처음 상태다
    const { gateway } = freshMock()

    // when·then: ' Tester '로 연결 테스트한다 → 성공한다
    await expect(gateway.setup.testDirectory({ ...SETUP_DIRECTORY_INPUT, testLoginId: ' Tester ' })).resolves.toEqual({ baseDn: expect.any(String) })
  })

  // 테스트 계정 아이디 형식이 틀리면 연결 테스트도 등록도 422 문구로 거절한다
  it.each(['bad id!', 'kim@corp.test', 'a'.repeat(65), ''])('rejects the test login id %j with the format message in both calls', async (testLoginId) => {
    // given: 최초 설정 처음 상태다
    const { gateway } = freshMock()
    const input = { ...SETUP_DIRECTORY_INPUT, testLoginId }

    // when·then: 연결 테스트와 등록 모두 422 "test_login_id: ..." 문구이고 저장되지 않는다
    await expectApiError(gateway.setup.testDirectory(input), 422, LOGIN_ID_FORMAT)
    await expectApiError(gateway.setup.saveDirectory(input), 422, LOGIN_ID_FORMAT)
    expect((await gateway.setup.status()).directoryDone).toBe(false)
  })

  // 테스트 비밀번호가 비었거나 NUL이 있거나 256자를 넘으면 문구로 거절한다
  it.each([
    ['', 'test_password: 비밀번호는 비어 있을 수 없습니다'],
    ['   ', 'test_password: 비밀번호는 비어 있을 수 없습니다'],
    ['a\u0000b', 'test_password: 비밀번호에는 NUL 문자를 쓸 수 없습니다'],
    ['a'.repeat(257), 'test_password: 비밀번호는 256자를 넘을 수 없습니다'],
  ])('rejects the test password %j with its message in both calls', async (testPassword, message) => {
    // given: 최초 설정 처음 상태다
    const { gateway } = freshMock()
    const input = { ...SETUP_DIRECTORY_INPUT, testPassword }

    // when·then: 연결 테스트와 등록 모두 422 문구이고 저장되지 않는다
    await expectApiError(gateway.setup.testDirectory(input), 422, message)
    await expectApiError(gateway.setup.saveDirectory(input), 422, message)
    expect((await gateway.setup.status()).directoryDone).toBe(false)
  })

  // 비밀번호의 앞뒤 공백은 지우지 않고 그대로 받는다
  it('accepts a test password with surrounding spaces as it is', async () => {
    // given: 최초 설정 처음 상태다
    const { gateway } = freshMock()

    // when·then: ' T-pass 1 '로 연결 테스트한다 → 성공한다
    await expect(gateway.setup.testDirectory({ ...SETUP_DIRECTORY_INPUT, testPassword: ' T-pass 1 ' })).resolves.toEqual({ baseDn: expect.any(String) })
  })

  // 호스트에 fail이 들어가면 연결 단계 실패(422 directory-verification-failed)이고 등록도 저장하지 않는다
  it('fails at the connect stage for a fail host in both calls without saving', async () => {
    // given: 최초 설정 처음 상태다
    const { gateway } = freshMock()
    const input = { ...SETUP_DIRECTORY_INPUT, host: 'fail.corp.test' }

    // when·then: 연결 테스트와 등록이 connect 단계 422이고 1단계는 끝나지 않는다
    const tested = await expectApiError(gateway.setup.testDirectory(input), 422, /연결 단계에서 실패했습니다/)
    const saved = await expectApiError(gateway.setup.saveDirectory(input), 422, /연결 단계에서 실패했습니다/)
    expect([tested.kind, tested.stage, saved.stage]).toEqual(['directory-verification-failed', 'connect', 'connect'])
    expect((await gateway.setup.status()).directoryDone).toBe(false)
  })
})
