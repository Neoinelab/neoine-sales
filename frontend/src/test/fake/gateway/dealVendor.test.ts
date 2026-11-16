/** Deal 등록·수정이 Vendor는 id(필수)로, Product는 선택 자유 텍스트로 받고 서버 검증 문구·History를 따른다. */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const UNKNOWN_VENDOR = '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.'
const VENDOR_REQUIRED = 'Vendor를 선택하세요.'
const TOO_LONG = 'Product는 200자 이내로 입력하세요.'

describe('deals.create vendor and product', () => {
  // 등록 응답은 Vendor를 {id, name}으로, Product를 다듬은 문자열로 돌려준다.
  it('returns the vendor as {id, name} and the product as a trimmed string', async () => {
    // given: sales 사용자(kim)
    const { gateway } = await mockAs('kim')
    // when: 앞뒤 공백이 든 Product로 Deal을 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { product: '  ITDR  ' }))
    // then: vendor는 {id, name}이고 product는 공백이 잘린 문자열이다
    expect(created.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(created.product).toBe('ITDR')
  })

  // Vendor 없이 등록하면 요청 형식 오류(422)이고 Deal이 만들어지지 않는다.
  it('rejects a deal without a vendor as a request-format error', async () => {
    // given: sales 사용자(kim)과 현재 Deal 수
    const { gateway } = await mockAs('kim')
    const before = (await gateway.deals.list({ limit: 100 })).total
    // when·then: vendorId가 없거나 null인 요청으로 등록한다 → 422다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { vendorId: null as unknown as number })), 422)
    const withoutVendor: Partial<ReturnType<typeof dealInput>> = dealInput(USER_ID.kim)
    delete withoutVendor.vendorId
    await expectApiError(gateway.deals.create(withoutVendor as ReturnType<typeof dealInput>), 422)
    // then: Deal 수가 그대로다
    expect((await gateway.deals.list({ limit: 100 })).total).toBe(before)
  })

  // Product는 선택이라 빈 값·공백은 빈 문자열로 저장한다.
  it('stores a blank product as an empty string', async () => {
    // given: sales 사용자(kim)
    const { gateway } = await mockAs('kim')
    // when: 빈 Product와 공백만 있는 Product로 등록한다
    const empty = await gateway.deals.create(dealInput(USER_ID.kim, { product: '' }))
    const blank = await gateway.deals.create(dealInput(USER_ID.kim, { product: '   ' }))
    // then: 둘 다 등록되고 product는 빈 문자열이다
    expect(empty.product).toBe('')
    expect(blank.product).toBe('')
  })

  // Product는 200자까지 허용하고 201자와 NUL은 거절한다.
  it('accepts 200 characters and rejects 201 and NUL', async () => {
    // given: sales 사용자(kim)
    const { gateway } = await mockAs('kim')
    // when: 200자·201자·NUL이 든 Product로 등록한다
    const result = await gateway.deals.create(dealInput(USER_ID.kim, { product: 'a'.repeat(200) }))
    // then: 200자는 등록되고 201자는 422 길이 문구, NUL은 422다
    expect(result).toBeDefined()
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { product: 'a'.repeat(201) })), 422, TOO_LONG)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { product: 'a\u0000b' })), 422)
  })

  // 검증 순서는 Deal Name, Vendor, Product, Owner 순이다.
  it('checks the vendor after the Deal Name, the product after the vendor and the owner after the product', async () => {
    // given: sales 사용자(kim)과 201자 Product
    const { gateway } = await mockAs('kim')
    const tooLong = 'a'.repeat(201)
    // when·then: 여러 칸이 틀린 요청으로 등록한다 → 가장 앞선 틀린 칸의 문구로 422가 난다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { name: ' ', vendorId: NO_SUCH_ID, product: tooLong })), 422, 'Deal Name을 입력하세요.')
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { vendorId: NO_SUCH_ID, product: tooLong })), 422, UNKNOWN_VENDOR)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.root, { product: tooLong })), 422, TOO_LONG)
  })
})

describe('deals.update vendor and product', () => {
  // 수정은 Product 텍스트를 다듬어 바꾸고 이력에 텍스트로 남긴다.
  it('replaces the product text, trims it and records it as text in the history', async () => {
    // given: Silverfort / MFA인 Deal과 현재 이력 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Silverfort / MFA
    const base = (await gateway.history.list(code, {})).length

    // when: 공백이 든 새 Product로 수정한다
    const updated = await gateway.deals.update(code, { product: '  Identity Threat ' })

    // then: product가 다듬은 값이고 이력에 Product 변경 1건이 남는다
    expect(updated.product).toBe('Identity Threat')
    const all = await gateway.history.list(code, {})
    expect(all.slice(0, all.length - base).map((h) => [h.category, h.target, h.before, h.after])).toEqual([
      ['other', 'Product', 'MFA', 'Identity Threat'],
    ])
  })

  // Product를 비우면 빈 값이 되고 이력에 남는다.
  it('clears the product and records it in the history', async () => {
    // given: Product가 MFA인 Deal과 현재 이력 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length

    // when: 공백만 있는 값으로 수정한다
    const updated = await gateway.deals.update(code, { product: '   ' })

    // then: Product가 ''이고 이력에 MFA에서 -로 한 건 남는다
    expect(updated.product).toBe('')
    const all = await gateway.history.list(code, {})
    expect(all.slice(0, all.length - base).map((h) => [h.target, h.before, h.after])).toEqual([['Product', 'MFA', '-']])
  })

  // 예전 solution 키는 모르는 필드라 등록·수정·목록 조회 모두 422이고 Deal은 바뀌지 않는다(2026-11-16 이름 변경, 별칭 없음).
  it('rejects the old solution key in create, update and list as an unknown field', async () => {
    // given: sales 사용자(kim)과 Product가 MFA인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const old = { solution: 'ITDR' }

    // when·then: 예전 키를 실어 등록·수정·목록 조회를 하면 모두 422다
    await expectApiError(gateway.deals.create({ ...dealInput(USER_ID.kim), ...old }), 422)
    await expectApiError(gateway.deals.update(code, old as never), 422)
    await expectApiError(gateway.deals.list(old as never), 422)

    // then: Deal의 Product는 그대로다
    expect((await gateway.deals.get(code)).product).toBe('MFA')
  })

  // Product를 보내지 않으면 값이 유지된다.
  it('keeps the product when it is not sent', async () => {
    // given: Product가 MFA인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: 이름만 바꿔 수정한다
    const updated = await gateway.deals.update(code, { name: '다른 이름' })
    // then: product가 MFA 그대로다
    expect(updated.product).toBe('MFA')
  })

  // Vendor만 바꾸면 Product는 유지되고 이력은 Vendor만 남는다.
  it('changes only the vendor, keeps the product and records the vendor alone', async () => {
    // given: Silverfort / MFA인 Deal과 현재 이력 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Silverfort / MFA
    const base = (await gateway.history.list(code, {})).length

    // when: Vendor를 Okta로 바꿔 수정한다
    const updated = await gateway.deals.update(code, { vendorId: seedVendorId('Okta') })

    // then: vendor는 Okta, product는 MFA이고 이력에 Vendor 변경 1건만 남는다
    expect(updated.vendor?.name).toBe('Okta')
    expect(updated.product).toBe('MFA')
    const all = await gateway.history.list(code, {})
    expect(all.slice(0, all.length - base).map((h) => [h.category, h.target, h.before, h.after])).toEqual([
      ['other', 'Vendor', 'Silverfort', 'Okta'],
    ])
  })

  // Vendor를 null로 보내면 거절하고 Vendor·Product를 유지한다.
  it('refuses to clear the vendor and keeps the vendor and the product', async () => {
    // given: Silverfort / MFA인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when·then: vendorId를 null로 수정한다 → 422와 'Vendor를 선택하세요.'다
    await expectApiError(gateway.deals.update(code, { vendorId: null as unknown as number }), 422, VENDOR_REQUIRED)
    // then: Vendor는 Silverfort, Product는 MFA 그대로다
    const stored = await gateway.deals.get(code)
    expect([stored.vendor?.name, stored.product]).toEqual(['Silverfort', 'MFA'])
  })

  // 같은 Vendor와 공백만 다른 같은 Product를 다시 보내면 이력이 남지 않는다.
  it('records nothing when the same vendor and the same product with spaces are sent again', async () => {
    // given: Silverfort / MFA인 Deal과 현재 이력 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length

    // when: 같은 Vendor와 공백이 붙은 같은 Product로 수정한다
    await gateway.deals.update(code, { vendorId: seedVendorId('Silverfort'), product: ' MFA ' })

    // then: 이력 건수가 그대로다
    expect((await gateway.history.list(code, {})).length).toBe(base)
  })

  // 대소문자만 바뀐 Product도 이력에 남긴다.
  it('records a case-only product change', async () => {
    // given: Product가 MFA인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when: Product를 mfa로 수정한다
    await gateway.deals.update(code, { product: 'mfa' })

    // then: Product 이력의 이전·이후 값이 MFA·mfa다
    const entry = (await gateway.history.list(code, {})).find((h) => h.target === 'Product')
    expect([entry?.before, entry?.after]).toEqual(['MFA', 'mfa'])
  })

  // Vendor 이름을 바꿔도 옛 이력 항목은 그대로다.
  it('keeps old history entries when a vendor is renamed', async () => {
    // given: admin이 Deal의 Vendor를 Okta로 바꿨다
    const admin = await mockAs('root')
    const code = dealCode(2)
    await admin.gateway.deals.update(code, { vendorId: seedVendorId('Okta') })
    // when: Vendor 이름을 'Okta Inc'로 바꾸고 이력을 읽는다
    await admin.gateway.vendors.rename(seedVendorId('Okta'), 'Okta Inc')

    const entry = (await admin.gateway.history.list(code, {})).find((h) => h.target === 'Vendor')

    // then: 이력의 이후 값은 옛 이름 Okta 그대로다
    expect(entry?.after).toBe('Okta')
  })
})
