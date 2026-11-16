/** Product가 빈 Deal: Product는 선택이라 비어 있어도 수정·변경 적용이 된다(서버와 같음). */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { buildLegacyProductSeed } from '../../fixtures/legacyProduct'
import { dealCode, mockAs } from '../testing'

describe('deals.update on a legacy deal with an empty product', () => {
  it('Vendor만 고치는 수정은 받아들이고 빈 Product를 그대로 둔다', async () => {
    // given: Product가 빈 레거시 Deal
    const { gateway } = await mockAs('kim', { seed: buildLegacyProductSeed })
    const code = dealCode(2)

    // when: Vendor만 담아 수정한다
    const updated = await gateway.deals.update(code, { vendorId: seedVendorId('Okta') })

    // then: Vendor가 바뀌고 Product는 빈 채로 남는다
    expect(updated.vendor?.name).toBe('Okta')
    expect(updated.product).toBe('')
  })

  it('Product 없이 사용자 수·매출을 고치는 수정은 받아들인다', async () => {
    // given: Product가 빈 레거시 Deal
    const { gateway } = await mockAs('kim', { seed: buildLegacyProductSeed })
    const code = dealCode(2)

    // when: Product 없이 사용자 수와 매출 금액만 수정한다
    const updated = await gateway.deals.update(code, { users: 12, revenueAmount: 777_000_000 })

    // then: 값이 바뀌고 Product는 빈 채로 남는다
    expect([updated.users, updated.revenueAmount, updated.product]).toEqual([12, 777_000_000, ''])
  })

  it.each(['', '   '])('보낸 Product가 공백이어도 거절하지 않고 빈 값으로 둔다 (%j)', async (sent) => {
    // given: Product가 빈 Deal
    const { gateway } = await mockAs('kim')

    // when: 공백 Product를 보내 수정한다
    const updated = await gateway.deals.update(dealCode(2), { product: sent })

    // then: 오류 없이 Product는 빈 채로 남는다
    expect(updated.product).toBe('')
  })

  it('applyChange로 매출 금액 하나를 바꾸는 것은 받아들인다', async () => {
    // given: Product가 빈 레거시 Deal
    const { gateway } = await mockAs('kim', { seed: buildLegacyProductSeed })
    const code = dealCode(2)

    // when: 매출 금액 하나를 변경 적용한다
    const result = await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 321_000_000 } })

    // then: 금액이 바뀌고 Product는 빈 채로 남는다
    expect([result.deal.revenueAmount, result.deal.product]).toEqual([321_000_000, ''])
  })
})
