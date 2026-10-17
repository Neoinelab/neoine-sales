import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'

const RANGE = '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'

describe('alerts.get (R-23)', () => {
  it('answers the default 14 days, never saved, to every role', async () => {
    for (const key of ['root', 'kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      expect(await gateway.alerts.get()).toEqual({ staleDays: 14, updatedAt: null, updatedBy: null })
    }
  })

  it('answers 401 without a session', async () => {
    const { gateway } = await mockAs(null)
    await expectApiError(gateway.alerts.get(), 401)
  })
})

describe('alerts.save (R-23)', () => {
  it('stores the value with the saver and the mock clock time', async () => {
    const { gateway } = await mockAs('root')

    const saved = await gateway.alerts.save(30)

    expect(saved).toMatchObject({ staleDays: 30, updatedAt: TEST_NOW, updatedBy: { id: 'u-root', role: 'admin' } })
    expect(await gateway.alerts.get()).toEqual(saved)
  })

  it('refuses sales and user with 403 and keeps the value', async () => {
    for (const key of ['kim', 'han'] as const) {
      const mock = await mockAs(key)
      await expectApiError(mock.gateway.alerts.save(30), 403)
      expect((await mock.gateway.alerts.get()).staleDays).toBe(14)
    }
  })

  it.each([0, 366, -1, 1.5, Number.NaN])('rejects %s with 422 and the range sentence, keeping the value', async (value) => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.alerts.save(value), 422, RANGE)

    expect((await gateway.alerts.get()).staleDays).toBe(14)
  })

  it.each([1, 365])('accepts the boundary %s', async (value) => {
    const { gateway } = await mockAs('root')

    expect((await gateway.alerts.save(value)).staleDays).toBe(value)
  })

  it('is reset to 14 by resetData', async () => {
    const mock = await mockAs('root')
    await mock.gateway.alerts.save(30)

    mock.control.resetData()

    expect(await mock.gateway.alerts.get()).toEqual({ staleDays: 14, updatedAt: null, updatedBy: null })
  })
})

describe('risk follows the saved threshold (R-19)', () => {
  // 시드 Deal 4(새론병원 PAM)는 마지막 갱신이 21일 전이고 Due Date가 미래다.
  it('turns the 21-day-old deal stale at 21 and healthy at 22 or at 30', async () => {
    const { gateway } = await mockAs('root')
    const riskOf = async () => (await gateway.deals.get(dealCode(4))).risk

    expect(await riskOf()).toBe('stale')
    await gateway.alerts.save(22)
    expect(await riskOf()).toBeNull()
    await gateway.alerts.save(21)
    expect(await riskOf()).toBe('stale')
    await gateway.alerts.save(30)
    expect(await riskOf()).toBeNull()
  })

  it('applies the threshold to the list rows too', async () => {
    const { gateway } = await mockAs('root')
    await gateway.alerts.save(30)

    const rows = (await gateway.deals.list({ limit: 100 })).items

    expect(rows.find((d) => d.code === dealCode(4))?.risk).toBeNull()
  })

  it('makes a 3-day-old deal stale at a 3-day threshold', async () => {
    const { gateway } = await mockAs('root')
    await gateway.alerts.save(3)

    // 시드 Deal 6(푸른물류 SSO)은 마지막 갱신 3일 전, Due Date 미래, Forecast pipeline.
    expect((await gateway.deals.get(dealCode(6))).risk).toBe('stale')
  })
})
