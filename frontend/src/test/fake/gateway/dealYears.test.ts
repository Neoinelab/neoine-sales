import { describe, expect, it } from 'vitest'
import { createMockGateway } from '../index'
import { dealInput, expectApiError, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

describe('deals.years', () => {
  it('returns null without deals', async () => {
    const mock = createMockGateway({ now: TEST_NOW, latency: false }) // 앱 기본 시드: 업무 데이터 없음
    await mock.gateway.auth.quickLogin(USER_ID.root)

    await expect(mock.gateway.deals.years()).resolves.toEqual({ earliestYear: null })
  })

  it('returns the year of the earliest Expected Close', async () => {
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 200 })).items
    const expected = Math.min(...all.map((d) => Number(d.revenueDate.slice(0, 4))))

    await expect(gateway.deals.years()).resolves.toEqual({ earliestYear: expected })
  })

  it('moves to an earlier year when an older deal is created and back when it is deleted', async () => {
    const { gateway } = await mockAs('kim')
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { revenueDate: '2015-03-01' }))
    await expect(gateway.deals.years()).resolves.toEqual({ earliestYear: 2015 })

    await gateway.deals.remove(created.code, created.code)

    expect((await gateway.deals.years()).earliestYear).toBeGreaterThan(2015)
  })

  it('follows an Expected Close update', async () => {
    const { gateway } = await mockAs('kim')
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { revenueDate: '2027-01-31' }))

    await gateway.deals.update(created.code, { revenueDate: '2012-06-30' })

    await expect(gateway.deals.years()).resolves.toEqual({ earliestYear: 2012 })
  })

  it('is readable by every role and needs a login', async () => {
    for (const key of ['root', 'kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      await expect(gateway.deals.years()).resolves.toHaveProperty('earliestYear')
    }
    const anonymous = await mockAs(null)
    await expectApiError(anonymous.gateway.deals.years(), 401)
  })
})
