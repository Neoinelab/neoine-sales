import { describe, expect, it } from 'vitest'
import { createHttpGateway } from './index'
import { NOT_IMPLEMENTED_MESSAGE, notImplemented } from './unsupported'

describe('notImplemented', () => {
  it('rejects with a 501 problem carrying the fixed message', async () => {
    const failure = notImplemented()

    await expect(failure).rejects.toMatchObject({ status: 501, kind: 'not-implemented', message: NOT_IMPLEMENTED_MESSAGE })
    expect(NOT_IMPLEMENTED_MESSAGE).toBe('아직 실제 서버와 연결되지 않은 기능입니다.')
  })
})

describe('domains without a server yet', () => {
  const gateway = createHttpGateway()

  it.each([
    ['attachments.list', () => gateway.attachments.list('20260101-AAAA')],
    ['attachments.remove', () => gateway.attachments.remove('att-1')],
    ['forecast.summary', () => gateway.forecast.summary({ year: 2026 })],
    ['setup.saveStorage', () => gateway.setup.saveStorage('/data')],
    ['setup.testStorage', () => gateway.setup.testStorage('/data')],
    ['settings.saveStorage', () => gateway.settings.saveStorage('/data')],
    ['settings.testStorage', () => gateway.settings.testStorage('/data')],
  ])('%s answers 501 without calling the server', async (_name, run) => {
    await expect(run()).rejects.toMatchObject({ status: 501, message: '아직 실제 서버와 연결되지 않은 기능입니다.' })
  })

  it('reports no storage settings yet', async () => {
    await expect(gateway.settings.getStorage()).resolves.toBeNull()
  })
})
