import { describe, expect, it } from 'vitest'
import { expectApiError, mockAs, newMock } from '../testing'

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
