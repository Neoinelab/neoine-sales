import { describe, expect, it } from 'vitest'
import { DIRECTORY_INPUT, BIND_PASSWORD } from '../../directoryFixtures'
import { expectApiError, newMock } from '../testing'

function freshMock() {
  const mock = newMock()
  mock.control.restartSetup()
  return mock
}

describe('최초 설정 테스트 계정 비저장', () => {
  it('tests without saving and registers with a scoped proof', async () => {
    const mock = freshMock()
    const result = await mock.gateway.setup.testDirectory(DIRECTORY_INPUT)
    expect(result).toEqual({ baseDn: 'dc=found,dc=test', testToken: expect.any(String) })
    expect((await mock.gateway.setup.status()).directoryDone).toBe(false)
    await mock.gateway.setup.saveDirectory({ ...DIRECTORY_INPUT, testToken: result.testToken })
    await mock.gateway.setup.saveStorage('/data/files')
    await mock.gateway.setup.registerAdmin('newadmin', 'pw')
    const saved = await mock.gateway.settings.getDirectory()
    expect(saved).toMatchObject({ host: DIRECTORY_INPUT.host, baseDn: result.baseDn })
    expect(JSON.stringify(saved)).not.toContain(BIND_PASSWORD)
    expect(saved).not.toHaveProperty('bindAccount')
  })
  it('requires valid test credentials and rejects untested endpoints', async () => {
    const { gateway } = freshMock()
    await expectApiError(gateway.setup.testDirectory({ ...DIRECTORY_INPUT, bindAccount: '' }), 422)
    await expectApiError(gateway.setup.testDirectory({ ...DIRECTORY_INPUT, bindPassword: '' }), 422)
    await expectApiError(gateway.setup.testDirectory({ ...DIRECTORY_INPUT, host: 'fail.test' }), 422)
    await expectApiError(gateway.setup.saveDirectory(DIRECTORY_INPUT), 422)
    const tested = await gateway.setup.testDirectory(DIRECTORY_INPUT)
    await expectApiError(gateway.setup.saveDirectory({ ...DIRECTORY_INPUT, host: 'other.test', testToken: tested.testToken }), 422)
    expect((await gateway.setup.status()).directoryDone).toBe(false)
  })
})
