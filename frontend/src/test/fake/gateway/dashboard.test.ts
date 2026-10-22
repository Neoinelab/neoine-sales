import { describe, expect, it } from 'vitest'
import { dealInput, expectApiError, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

/**
 * Fake 대시보드 규칙(서버와 같은 규칙을 시드에서 직접 계산): Lost 제외, 분기 경계, 오늘 기준 이번 달·분기,
 * 주의 타일의 기간 무시. 기준일은 Fake 시계(2026-10-15)다. 서버와의 일치는 계약 스위트(dashboard.contract)가 본다.
 */

const NOW_2026_12_31 = '2026-12-31T12:00:00+09:00'

describe('Fake dashboard.summary', () => {
  it('excludes Lost deals from the forecast tiles and the status items but keeps Won', async () => {
    const { gateway } = await mockAs('kim', { now: TEST_NOW })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Lost 제외', forecastKey: 'lost', statusKey: 'price_negotiation', revenueDate: '2031-05-05', revenueAmount: 9_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Won 포함', forecastKey: 'won', statusKey: 'contract_completed', revenueDate: '2031-05-06', revenueAmount: 4_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Open 포함', forecastKey: 'commit', statusKey: 'prospecting', revenueDate: '2031-05-07', revenueAmount: 1_000_000 }))

    const { forecast, statuses } = await gateway.dashboard.summary({ year: 2031 })

    expect(forecast.columns.map((c) => c.key)).not.toContain('lost')
    expect(forecast.cells.commit).toEqual({ count: 1, amount: 1_000_000 })
    expect(forecast.cells.won).toEqual({ count: 1, amount: 4_000_000 })
    expect(forecast.openTotal).toEqual({ count: 1, amount: 1_000_000 })
    expect(statuses.items.find((i) => i.key === 'price_negotiation')).toMatchObject({ count: 0, amount: 0 })
    expect(statuses.items.find((i) => i.key === 'contract_completed')).toMatchObject({ count: 1, amount: 4_000_000 })
    expect(statuses.total).toEqual({ count: 2, amount: 5_000_000 })
  })

  it('lists every status code in order even when no deal matches', async () => {
    const { gateway } = await mockAs('kim', { now: TEST_NOW })

    const { statuses } = await gateway.dashboard.summary({ year: 2099 })

    expect(statuses.items.map((i) => i.key)).toEqual(['prospecting', 'introduction', 'poc_preparation', 'poc_completed', 'technical_evaluation', 'price_negotiation', 'contract_completed'])
    expect(statuses.items.every((i) => i.count === 0 && i.amount === 0)).toBe(true)
    expect(statuses.total).toEqual({ count: 0, amount: 0 })
  })

  it('puts December 31 in Q4 and January 1 in the next year Q1', async () => {
    const { gateway } = await mockAs('kim', { now: TEST_NOW })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '경계 12/31', revenueDate: '2032-12-31', forecastKey: 'commit', revenueAmount: 7_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '경계 1/1', revenueDate: '2033-01-01', forecastKey: 'best', revenueAmount: 3_000_000 }))

    const y2032 = await gateway.dashboard.summary({ year: 2032 })
    const y2033 = await gateway.dashboard.summary({ year: 2033 })

    expect(y2032.quarters[3]?.total).toEqual({ count: 1, amount: 7_000_000 })
    expect(y2032.quarters[0]?.total).toEqual({ count: 0, amount: 0 })
    expect(y2033.quarters[0]?.total).toEqual({ count: 1, amount: 3_000_000 })
  })

  it('answers four quarters in order whatever quarter is chosen, and narrows only the top parts', async () => {
    const { gateway } = await mockAs('kim', { now: TEST_NOW })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Q1', revenueDate: '2034-02-01', forecastKey: 'commit', revenueAmount: 1_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: 'Q3', revenueDate: '2034-08-01', forecastKey: 'commit', revenueAmount: 2_000_000 }))

    const q3 = await gateway.dashboard.summary({ year: 2034, quarter: 3 })

    expect(q3.quarters.map((q) => q.quarter)).toEqual([1, 2, 3, 4])
    expect(q3.quarters.map((q) => q.total.count)).toEqual([1, 0, 1, 0])
    expect(q3.statuses.total).toEqual({ count: 1, amount: 2_000_000 })
    expect(q3.forecast.cells.commit).toEqual({ count: 1, amount: 2_000_000 })
  })

  it('counts this month and this quarter from the Fake clock business date, open deals only', async () => {
    const { gateway, clock } = await mockAs('kim', { now: TEST_NOW })
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '이번 달 Open', revenueDate: '2026-10-30', forecastKey: 'commit' }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '이번 달 Lost', revenueDate: '2026-10-31', forecastKey: 'lost' }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '다음 달 Open', revenueDate: '2026-12-01', forecastKey: 'best' }))

    const before = (await gateway.dashboard.summary({ year: 2020 })).attention
    const openIn = async (month: number) =>
      (await gateway.deals.list({ year: 2026, month, limit: 200 })).items.filter((d) => d.forecastKey !== 'lost' && d.forecastKey !== 'won').length
    const octoberOpen = await openIn(10)
    clock.setNow(NOW_2026_12_31)
    const after = (await gateway.dashboard.summary({ year: 2020 })).attention

    expect(before.closingThisMonth).toMatchObject({ year: 2026, month: 10, count: octoberOpen })
    expect(octoberOpen).toBeGreaterThanOrEqual(1)
    expect(before.closingThisQuarter).toMatchObject({ year: 2026, quarter: 4 })
    expect(after.closingThisMonth).toMatchObject({ year: 2026, month: 12, count: await openIn(12) })
    expect(after.closingThisQuarter).toMatchObject({ year: 2026, quarter: 4, count: before.closingThisQuarter.count })
  })

  it('switches to the next year on January 1', async () => {
    const { gateway, clock } = await mockAs('kim', { now: TEST_NOW })
    clock.setNow('2027-01-01T12:00:00+09:00')

    const { attention, today } = await gateway.dashboard.summary({ year: 2026 })

    expect(today).toBe('2027-01-01')
    expect(attention.closingThisMonth).toMatchObject({ year: 2027, month: 1 })
    expect(attention.closingThisQuarter).toMatchObject({ year: 2027, quarter: 1 })
  })

  it('ignores year and quarter for the attention counts but follows the owner', async () => {
    const { gateway } = await mockAs('kim', { now: TEST_NOW })

    const whole = await gateway.dashboard.summary({ year: 2026 })
    const other = await gateway.dashboard.summary({ year: 1999, quarter: 2 })
    const mine = await gateway.dashboard.summary({ year: 1999, ownerId: USER_ID.kim })

    expect(other.attention).toEqual(whole.attention)
    expect(mine.attention.overdue).toBeLessThanOrEqual(whole.attention.overdue)
    expect(mine.attention.stale).toBeLessThanOrEqual(whole.attention.stale)
  })

  it('rejects a year or quarter outside the range with 422', async () => {
    const { gateway } = await mockAs('kim', { now: TEST_NOW })

    await expectApiError(gateway.dashboard.summary({ year: 1899 }), 422)
    await expectApiError(gateway.dashboard.summary({ year: 2026, quarter: 5 as never }), 422)
  })

  it('answers 401 without a login', async () => {
    const { gateway } = await mockAs(null, { now: TEST_NOW })

    await expectApiError(gateway.dashboard.summary({ year: 2026 }), 401)
  })
})
