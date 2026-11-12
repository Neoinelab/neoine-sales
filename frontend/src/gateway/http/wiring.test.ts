import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpGateway } from './index'
import { stubNetworkDown } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

describe('every domain is wired to the server', () => {
  const gateway = createHttpGateway()

  // 각 도메인 호출이 서버에 연결되어 있다(서버 시각 호출 time.get 포함).
  // 테스트 코드: TM-029
  it.each([
    ['time.get', () => gateway.time.get()],
    ['forecast.summary', () => gateway.forecast.summary({ year: 2026 })],
    ['attachments.list', () => gateway.attachments.list('20260101-AAAA')],
    ['attachments.remove', () => gateway.attachments.remove(1)],
    ['attachments.download', () => gateway.attachments.download(1)],
    ['partnerMeetings.list', () => gateway.partnerMeetings.list({ sort: 'meetingDate', order: 'desc' }, 0, 10)],
    ['setup.saveStorage', () => gateway.setup.saveStorage('/data')],
    ['setup.testStorage', () => gateway.setup.testStorage('/data')],
    ['settings.getStorage', () => gateway.settings.getStorage()],
    ['settings.saveStorage', () => gateway.settings.saveStorage('/data')],
    ['settings.testStorage', () => gateway.settings.testStorage('/data')],
  ])('%s is wired to the server (a down server is a network error, not 501)', async (_name, run) => {
    // given: 서버가 꺼져 있다
    stubNetworkDown()

    // when·then: 각 호출은 501이 아니라 네트워크 오류(status 0)로 실패한다
    await expect(run()).rejects.toMatchObject({ status: 0 })
  })
})
