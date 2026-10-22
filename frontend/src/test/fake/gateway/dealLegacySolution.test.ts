/** Solution이 빈 레거시 Deal: 서버처럼 Solution을 보낸 때만 검사한다(리뷰 후속 결정). */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { buildLegacySolutionSeed } from '../../fixtures/legacySolution'
import { dealCode, expectApiError, mockAs } from '../testing'

const REQUIRED = 'Solution을 입력하세요.'

describe('deals.update on a legacy deal with an empty solution', () => {
  it('accepts a vendor-only patch and keeps the empty solution', async () => {
    const { gateway } = await mockAs('kim', { seed: buildLegacySolutionSeed })
    const code = dealCode(2)

    const updated = await gateway.deals.update(code, { vendorId: seedVendorId('Okta') })

    expect(updated.vendor?.name).toBe('Okta')
    expect(updated.solution).toBe('')
  })

  it('accepts a users and revenue patch without solution', async () => {
    const { gateway } = await mockAs('kim', { seed: buildLegacySolutionSeed })
    const code = dealCode(2)

    const updated = await gateway.deals.update(code, { users: 12, revenueAmount: 777_000_000 })

    expect([updated.users, updated.revenueAmount, updated.solution]).toEqual([12, 777_000_000, ''])
  })

  it.each(['', '   '])('still rejects a blank solution that is sent (%j)', async (sent) => {
    const { gateway } = await mockAs('kim', { seed: buildLegacySolutionSeed })

    await expectApiError(gateway.deals.update(dealCode(2), { solution: sent }), 422, REQUIRED)
  })

  it('accepts a single revenue change through applyChange', async () => {
    const { gateway } = await mockAs('kim', { seed: buildLegacySolutionSeed })
    const code = dealCode(2)

    const result = await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 321_000_000 } })

    expect([result.deal.revenueAmount, result.deal.solution]).toEqual([321_000_000, ''])
  })
})
