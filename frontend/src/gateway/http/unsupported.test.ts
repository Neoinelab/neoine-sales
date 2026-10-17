import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpGateway } from './index'
import { stubNetworkDown } from './testHelpers'
import { NOT_IMPLEMENTED_MESSAGE, notImplemented } from './unsupported'

afterEach(() => vi.unstubAllGlobals())

describe('notImplemented', () => {
  it('rejects with a 501 problem carrying the fixed message', async () => {
    const failure = notImplemented()

    await expect(failure).rejects.toMatchObject({ status: 501, kind: 'not-implemented', message: NOT_IMPLEMENTED_MESSAGE })
    expect(NOT_IMPLEMENTED_MESSAGE).toBe('아직 실제 서버와 연결되지 않은 기능입니다.')
  })
})

describe('domains without a server yet', () => {
  const gateway = createHttpGateway()

  it('forecast.summary answers 501 without calling the server', async () => {
    await expect(gateway.forecast.summary({ year: 2026 })).rejects.toMatchObject({
      status: 501,
      message: '아직 실제 서버와 연결되지 않은 기능입니다.',
    })
  })

  it.each([
    ['attachments.list', () => gateway.attachments.list('20260101-AAAA')],
    ['attachments.remove', () => gateway.attachments.remove('att-1')],
    ['attachments.download', () => gateway.attachments.download('att-1')],
    ['setup.saveStorage', () => gateway.setup.saveStorage('/data')],
    ['setup.testStorage', () => gateway.setup.testStorage('/data')],
    ['settings.getStorage', () => gateway.settings.getStorage()],
    ['settings.saveStorage', () => gateway.settings.saveStorage('/data')],
    ['settings.testStorage', () => gateway.settings.testStorage('/data')],
  ])('%s is wired to the server (a down server is a network error, not 501)', async (_name, run) => {
    stubNetworkDown()

    await expect(run()).rejects.toMatchObject({ status: 0 })
  })
})
