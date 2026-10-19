import { describe, expect, it } from 'vitest'
import { dealInput } from './testing'
import { createClock } from './clock'
import { createMockGateway } from './index'
import { emptyBusinessSeed } from './seed'

const NOW = '2026-10-15T09:00:00+09:00'

/** 테스트 도우미(`newMock`)를 거치지 않은 "앱 기본" 게이트웨이(시드 옵션 없음). */
async function appDefault() {
  const mock = createMockGateway({ now: NOW, latency: false })
  await mock.gateway.auth.quickLogin('u-root')
  return mock
}

describe('앱 기본 시드에는 샘플 업무 데이터가 없다', () => {
  it('has no deals, contacts, actions, history or attachments in the default seed', () => {
    const data = emptyBusinessSeed(createClock(NOW))
    expect(data.deals).toEqual([])
    expect(data.contacts).toEqual([])
    expect(data.actions).toEqual([])
    expect(data.history).toEqual([])
    expect(data.attachments).toEqual([])
  })

  it('lists nothing through the gateway of a default instance', async () => {
    const { gateway } = await appDefault()
    const deals = await gateway.deals.list({ limit: 100 })
    expect(deals.items).toEqual([])
    expect(deals.total).toBe(0)
    expect((await gateway.contacts.list({ limit: 100 })).items).toEqual([])
    expect(await gateway.contacts.companies('customer')).toEqual([])
    expect(await gateway.contacts.companies('partner')).toEqual([])
  })

  it('keeps default codes, BANT labels and login accounts', async () => {
    const { gateway } = await appDefault()
    const codes = await gateway.codes.all()
    expect(codes.statuses).toHaveLength(7)
    expect(codes.forecasts).toHaveLength(6)
    expect((await gateway.labels.list()).length).toBeGreaterThan(0)
    const users = await gateway.users.list('all')
    expect(users.map((u) => u.loginId)).toEqual(expect.arrayContaining(['root', 'kim', 'park', 'han', 'old']))
  })

  it('returns to the empty business data on resetData after a deal was created', async () => {
    const { gateway, control } = await appDefault()
    await gateway.deals.create(dealInput('u-kim', { vendorId: null, solutionId: null }))
    expect((await gateway.deals.list({ limit: 100 })).total).toBe(1)
    control.resetData()
    expect((await gateway.deals.list({ limit: 100 })).total).toBe(0)
    expect(await gateway.contacts.companies('customer')).toEqual([])
  })
})
