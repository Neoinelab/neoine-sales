import { describe, expect, it } from 'vitest'
import { dealCode, dealInput, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

const DAY_MS = 86_400_000

async function setup() {
  const mock = await mockAs('kim')
  const created = await mock.gateway.deals.create(dealInput(USER_ID.kim))
  return { ...mock, code: created.code, created }
}

describe('Status 진입 시각 (R-22, R-21)', () => {
  it('starts at registration with statusDays 0', async () => {
    const { created } = await setup()

    expect(created).toMatchObject({ statusChangedAt: TEST_NOW, statusDays: 0 })
  })

  it('counts statusDays by calendar days of the mock clock, on the detail and the list row', async () => {
    const { gateway, clock, code } = await setup()
    clock.advance(3 * DAY_MS)

    expect((await gateway.deals.get(code)).statusDays).toBe(3)
    const row = (await gateway.deals.list({ keyword: code })).items[0]
    expect(row).toMatchObject({ statusChangedAt: TEST_NOW, statusDays: 3 })
  })

  it('keeps statusChangedAt when only the forecast changes via update', async () => {
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    const updated = await gateway.deals.update(code, { forecastKey: 'best' })

    expect(updated.statusChangedAt).toBe(TEST_NOW)
  })

  it('keeps statusChangedAt for other fields and for sending the same status again', async () => {
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    await gateway.deals.update(code, { name: '이름 변경' })
    const same = await gateway.deals.update(code, { statusKey: 'prospecting' })

    expect(same.statusChangedAt).toBe(TEST_NOW)
    expect(same.statusDays).toBe(1)
  })

  it('sets statusChangedAt to the request time when update changes the status', async () => {
    const { gateway, clock, code } = await setup()
    clock.advance(2 * DAY_MS)

    const updated = await gateway.deals.update(code, { statusKey: 'introduction' })

    expect(updated.statusChangedAt).toBe(clock.now())
    expect(updated.statusDays).toBe(0)
  })

  it('moves it on applyChange of the status but not of the forecast or the amount', async () => {
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    const forecast = await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'best' } })
    const amount = await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 700_000_000 } })
    expect([forecast.deal.statusChangedAt, amount.deal.statusChangedAt]).toEqual([TEST_NOW, TEST_NOW])

    const status = await gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'introduction' } })
    expect(status.deal.statusChangedAt).toBe(clock.now())
  })

  it('moves it when the contract completion also changes the status (forecast to Won)', async () => {
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)

    const result = await gateway.deals.applyChange(code, {
      change: { field: 'forecastKey', value: 'won' },
      resolution: { revenueAmount: 500_000_000, revenueDate: '2026-10-16' },
    })

    expect(result.deal.statusKey).toBe('contract_completed')
    expect(result.deal.statusChangedAt).toBe(clock.now())
  })

  it('moves it only when the action registration carries a status change', async () => {
    const { gateway, clock, code } = await setup()
    clock.advance(DAY_MS)
    const base = { type: { name: '미팅' }, progress: '방문', nextAction: '견적', dueDate: '2026-10-30', memo: '' }

    await gateway.actions.create(code, base)
    expect((await gateway.deals.get(code)).statusChangedAt).toBe(TEST_NOW)

    await gateway.actions.create(code, { ...base, statusChanges: [{ change: { field: 'statusKey', value: 'introduction' } }] })
    expect((await gateway.deals.get(code)).statusChangedAt).toBe(clock.now())
  })

  it('does not move it for a procurement edit on a seed deal', async () => {
    const { gateway, clock } = await mockAs('kim')
    const code = dealCode(1)
    const before = (await gateway.deals.get(code)).statusChangedAt
    clock.advance(DAY_MS)

    const after = await gateway.deals.update(code, { procurement: '변경' })

    expect(after.statusChangedAt).toBe(before)
  })
})
