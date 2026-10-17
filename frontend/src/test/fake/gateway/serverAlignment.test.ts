/** P1 R4: mock을 서버 규칙(domain/deal/values.py, ports/deal_repository.py)에 맞춘 회귀. 계획 8장 "mock 정렬". */

import { describe, expect, it } from 'vitest'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'

describe('deals.facets', () => {
  it('leaves empty vendor and solution out', async () => {
    const { gateway } = await mockAs('kim')
    await gateway.deals.create(dealInput('u-kim', { vendor: '', solution: '' }))

    const facets = await gateway.deals.facets()

    expect(facets.vendors).not.toContain('')
    expect(facets.solutions).not.toContain('')
    expect(facets.vendors).toContain('Silverfort')
  })
})

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

    await expectApiError(gateway.deals.create(dealInput('u-kim', { users: 2_147_483_648 })), 422, 'Users는 1 이상의 정수로 입력하세요.')
    await expectApiError(gateway.deals.update(dealCode(2), { users: 2_147_483_648 }), 422, 'Users는 1 이상의 정수로 입력하세요.')
  })
})

describe('deals.list quarter', () => {
  it('rejects a quarter without a year with 422', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.list({ quarter: 2 }), 422, '분기는 연도와 함께 선택하세요.')
  })

  it('still accepts a year alone and a year with a quarter', async () => {
    const { gateway } = await mockAs('kim')

    await expect(gateway.deals.list({ year: 2026 })).resolves.toHaveProperty('total')
    await expect(gateway.deals.list({ year: 2026, quarter: 4 })).resolves.toHaveProperty('total')
  })
})

describe('trim before the length check (P2 carry-over 1, AC-24)', () => {
  it('accepts a 100 character Vendor with surrounding spaces and stores it trimmed', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput('u-kim', { vendor: `  ${'v'.repeat(100)}  ` }))

    expect(created.vendor).toBe('v'.repeat(100))
    expect((await gateway.deals.get(created.code)).vendor).toBe('v'.repeat(100))
  })

  it('rejects 101 characters of Vendor even after trimming', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.create(dealInput('u-kim', { vendor: ` ${'v'.repeat(101)} ` })), 422, 'Vendor는 100자 이내로 입력하세요.')
  })

  it('accepts a 200 character Solution with surrounding spaces and stores it trimmed', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput('u-kim', { solution: `  ${'s'.repeat(200)}  ` }))

    expect(created.solution).toBe('s'.repeat(200))
  })

  it('rejects 201 characters of Solution even after trimming', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.create(dealInput('u-kim', { solution: ` ${'s'.repeat(201)} ` })), 422, 'Solution은 200자 이내로 입력하세요.')
  })

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

  it('trims the three fields on update as well, within their limits', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    const updated = await gateway.deals.update(code, {
      vendor: `  ${'v'.repeat(100)}  `,
      solution: `  ${'s'.repeat(200)}  `,
      procurement: `  ${'가'.repeat(500)}  `,
    })

    expect(updated).toMatchObject({ vendor: 'v'.repeat(100), solution: 's'.repeat(200), procurement: '가'.repeat(500) })
  })

  it('rejects an over-long trimmed Vendor on update and keeps the stored value', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = (await gateway.deals.get(code)).vendor

    await expectApiError(gateway.deals.update(code, { vendor: ` ${'v'.repeat(101)} ` }), 422, 'Vendor는 100자 이내로 입력하세요.')

    expect((await gateway.deals.get(code)).vendor).toBe(before)
  })

  it('lists a padded Vendor in the facets without the spaces', async () => {
    const { gateway } = await mockAs('kim')
    await gateway.deals.create(dealInput('u-kim', { vendor: ' Okta ' }))

    const facets = await gateway.deals.facets()

    expect(facets.vendors).toContain('Okta')
    expect(facets.vendors).not.toContain(' Okta ')
  })

  it('lists a padded Solution in the facets without the spaces', async () => {
    const { gateway } = await mockAs('kim')
    await gateway.deals.create(dealInput('u-kim', { solution: ' PAM ' }))

    const facets = await gateway.deals.facets()

    expect(facets.solutions).toContain('PAM')
    expect(facets.solutions).not.toContain(' PAM ')
  })
})
