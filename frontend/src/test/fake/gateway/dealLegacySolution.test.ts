/** Solution이 빈 레거시 Deal: 서버처럼 Solution을 보낸 때만 검사한다. */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { buildLegacySolutionSeed } from '../../fixtures/legacySolution'
import { dealCode, expectApiError, mockAs } from '../testing'

const REQUIRED = 'Solution을 입력하세요.'

describe('deals.update on a legacy deal with an empty solution', () => {
  it('Vendor만 고치는 수정은 받아들이고 빈 Solution을 그대로 둔다', async () => {
    // given: Solution이 빈 레거시 Deal
    const { gateway } = await mockAs('kim', { seed: buildLegacySolutionSeed })
    const code = dealCode(2)

    // when: Vendor만 담아 수정한다
    const updated = await gateway.deals.update(code, { vendorId: seedVendorId('Okta') })

    // then: Vendor가 바뀌고 Solution은 빈 채로 남는다
    expect(updated.vendor?.name).toBe('Okta')
    expect(updated.solution).toBe('')
  })

  it('Solution 없이 사용자 수·매출을 고치는 수정은 받아들인다', async () => {
    // given: Solution이 빈 레거시 Deal
    const { gateway } = await mockAs('kim', { seed: buildLegacySolutionSeed })
    const code = dealCode(2)

    // when: Solution 없이 사용자 수와 매출 금액만 수정한다
    const updated = await gateway.deals.update(code, { users: 12, revenueAmount: 777_000_000 })

    // then: 값이 바뀌고 Solution은 빈 채로 남는다
    expect([updated.users, updated.revenueAmount, updated.solution]).toEqual([12, 777_000_000, ''])
  })

  it.each(['', '   '])('보낸 Solution이 공백이면 여전히 거절한다 (%j)', async (sent) => {
    // given: Solution이 빈 레거시 Deal
    const { gateway } = await mockAs('kim', { seed: buildLegacySolutionSeed })

    // when·then: 공백 Solution을 보내 수정하면 필수 안내 문구로 422가 된다
    await expectApiError(gateway.deals.update(dealCode(2), { solution: sent }), 422, REQUIRED)
  })

  it('applyChange로 매출 금액 하나를 바꾸는 것은 받아들인다', async () => {
    // given: Solution이 빈 레거시 Deal
    const { gateway } = await mockAs('kim', { seed: buildLegacySolutionSeed })
    const code = dealCode(2)

    // when: 매출 금액 하나를 변경 적용한다
    const result = await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 321_000_000 } })

    // then: 금액이 바뀌고 Solution은 빈 채로 남는다
    expect([result.deal.revenueAmount, result.deal.solution]).toEqual([321_000_000, ''])
  })
})
