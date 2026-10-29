import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpGateway } from './index'
import { stubNetworkDown } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

describe('every domain is wired to the server', () => {
  const gateway = createHttpGateway()

  it.each([
    ['time.get', () => gateway.time.get()],
    ['forecast.summary', () => gateway.forecast.summary({ year: 2026 })],
    ['attachments.list', () => gateway.attachments.list('20260101-AAAA')],
    ['attachments.remove', () => gateway.attachments.remove(1)],
    ['attachments.download', () => gateway.attachments.download(1)],
    ['partnerMeetings.list', () => gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 10)],
    ['partnerMeetings.dealOptions', () => gateway.partnerMeetings.dealOptions('코어테크')],
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
