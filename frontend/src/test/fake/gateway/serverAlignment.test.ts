/** P1 R4: mock을 서버 규칙(domain/deal/values.py, ports/deal_repository.py)에 맞춘 회귀. 계획 8장 "mock 정렬". */

import { describe, expect, it } from 'vitest'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'

describe('Deal Name length', () => {
  it('accepts 200 characters on create', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput('u-kim', { name: 'a'.repeat(200) }))

    expect(created.name).toHaveLength(200)
  })

  it('rejects 201 characters on create with the server message', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.create(dealInput('u-kim', { name: 'a'.repeat(201) })), 422, 'Deal Name은 200자 이내로 입력하세요.')
  })

  it('rejects 201 characters on update and keeps the name', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = (await gateway.deals.get(code)).name

    await expectApiError(gateway.deals.update(code, { name: 'a'.repeat(201) }), 422, 'Deal Name은 200자 이내로 입력하세요.')

    expect((await gateway.deals.get(code)).name).toBe(before)
  })
})

describe('procurement length', () => {
  it('accepts 500 characters', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput('u-kim', { procurement: '가'.repeat(500) }))

    expect(created.procurement).toHaveLength(500)
  })

  it('rejects 501 characters on create and on update', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.create(dealInput('u-kim', { procurement: '가'.repeat(501) })), 422, '구매절차는 500자 이내로 입력하세요.')
    await expectApiError(gateway.deals.update(dealCode(2), { procurement: '가'.repeat(501) }), 422, '구매절차는 500자 이내로 입력하세요.')
  })
})

describe('Users upper bound', () => {
  it('accepts the largest integer the server stores (2147483647)', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput('u-kim', { users: 2_147_483_647 }))

    expect(created.users).toBe(2_147_483_647)
  })

  it('rejects one more with the Users message on create and on update', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.create(dealInput('u-kim', { users: 2_147_483_648 })), 422, 'Users는 0 이상의 정수로 입력하세요.')
    await expectApiError(gateway.deals.update(dealCode(2), { users: 2_147_483_648 }), 422, 'Users는 0 이상의 정수로 입력하세요.')
  })

  it('accepts Users of zero on create', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput('u-kim', { users: 0 }))

    expect(created.users).toBe(0)
  })
})

describe('deals.list quarter', () => {
  it('accepts a quarter without a year and reads it as this year (AC-19)', async () => {
    const { gateway } = await mockAs('kim') // Fake 시계 2026-10-15

    const quarterOnly = await gateway.deals.list({ quarter: 4, limit: 100 })
    const explicit = await gateway.deals.list({ year: 2026, quarter: 4, limit: 100 })

    expect(quarterOnly.total).toBeGreaterThan(0)
    expect(quarterOnly.items.map((d) => d.code)).toEqual(explicit.items.map((d) => d.code))
  })

  it('still accepts a year alone and a year with a quarter', async () => {
    const { gateway } = await mockAs('kim')

    await expect(gateway.deals.list({ year: 2026 })).resolves.toHaveProperty('total')
    await expect(gateway.deals.list({ year: 2026, quarter: 4 })).resolves.toHaveProperty('total')
  })
})

describe('trim before the length check (P2 carry-over 1, AC-24; Vendor·Solution 길이는 이제 관리 목록 규칙)', () => {
  it('accepts a 500 character procurement with surrounding spaces and stores it trimmed', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput('u-kim', { procurement: `  ${'가'.repeat(500)}  ` }))

    expect(created.procurement).toBe('가'.repeat(500))
  })

  it('rejects 501 characters of procurement even after trimming', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(
      gateway.deals.create(dealInput('u-kim', { procurement: ` ${'가'.repeat(501)} ` })),
      422,
      '구매절차는 500자 이내로 입력하세요.',
    )
  })

  it('trims the procurement on update as well, within its limit', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    const updated = await gateway.deals.update(code, { procurement: `  ${'가'.repeat(500)}  ` })

    expect(updated.procurement).toBe('가'.repeat(500))
  })

})
