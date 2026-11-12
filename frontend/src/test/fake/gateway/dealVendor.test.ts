/** Deal 등록·수정이 Vendor는 id로, Solution은 필수 자유 텍스트로 받고 서버 검증 문구·History를 따른다. */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const UNKNOWN_VENDOR = '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.'
const REQUIRED = 'Solution을 입력하세요.'
const TOO_LONG = 'Solution은 200자 이내로 입력하세요.'

describe('deals.create vendor and solution', () => {
  // 등록 응답은 Vendor를 {id, name}으로, Solution을 다듬은 문자열로 돌려준다.
  it('returns the vendor as {id, name} and the solution as a trimmed string', async () => {
    // given: sales 사용자(kim)
    const { gateway } = await mockAs('kim')
    // when: 앞뒤 공백이 든 Solution으로 Deal을 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { solution: '  ITDR  ' }))
    // then: vendor는 {id, name}이고 solution은 공백이 잘린 문자열이다
    expect(created.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(created.solution).toBe('ITDR')
  })

  // Vendor 없이 Solution만으로 등록할 수 있다.
  it('accepts a solution without a vendor', async () => {
    // given: sales 사용자(kim)
    const { gateway } = await mockAs('kim')
    // when: Vendor 없이 Solution만 넣어 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { vendorId: null, solution: 'ITDR' }))
    // then: vendor는 null이고 solution은 입력 그대로다
    expect(created.vendor).toBeNull()
    expect(created.solution).toBe('ITDR')
  })

  // 빈 Solution은 등록할 수 없다.
  it('requires a non-blank solution', async () => {
    // given: sales 사용자(kim)
    const { gateway } = await mockAs('kim')
    // when·then: 빈 Solution과 공백만 있는 Solution으로 등록한다 → 422와 'Solution을 입력하세요.'다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { solution: '' })), 422, REQUIRED)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { solution: '   ' })), 422, REQUIRED)
  })

  // Solution은 200자까지 허용하고 201자와 NUL은 거절한다.
  it('accepts 200 characters and rejects 201 and NUL', async () => {
    // given: sales 사용자(kim)
    const { gateway } = await mockAs('kim')
    // when: 200자·201자·NUL이 든 Solution으로 등록한다
    const result = await gateway.deals.create(dealInput(USER_ID.kim, { solution: 'a'.repeat(200) }))
    // then: 200자는 등록되고 201자는 422 길이 문구, NUL은 422다
    expect(result).toBeDefined()
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { solution: 'a'.repeat(201) })), 422, TOO_LONG)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { solution: 'a\u0000b' })), 422)
  })

  // 검증 순서는 Deal Name, Vendor, Solution, Owner 순이다.
  it('checks the vendor after the Deal Name, the solution after the vendor and the owner after the solution', async () => {
    // given: sales 사용자(kim)과 201자 Solution
    const { gateway } = await mockAs('kim')
    const tooLong = 'a'.repeat(201)
    // when·then: 여러 칸이 틀린 요청으로 등록한다 → 가장 앞선 틀린 칸의 문구로 422가 난다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { name: ' ', vendorId: NO_SUCH_ID, solution: tooLong })), 422, 'Deal Name을 입력하세요.')
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { vendorId: NO_SUCH_ID, solution: tooLong })), 422, UNKNOWN_VENDOR)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.root, { solution: tooLong })), 422, TOO_LONG)
  })
})

describe('deals.update vendor and solution', () => {
  // 수정은 Solution 텍스트를 다듬어 바꾸고 이력에 텍스트로 남긴다.
  it('replaces the solution text, trims it and records it as text in the history', async () => {
    // given: Silverfort / MFA인 Deal과 현재 이력 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Silverfort / MFA
    const base = (await gateway.history.list(code, {})).length

    // when: 공백이 든 새 Solution으로 수정한다
    const updated = await gateway.deals.update(code, { solution: '  Identity Threat ' })

    // then: solution이 다듬은 값이고 이력에 Solution 변경 1건이 남는다
    expect(updated.solution).toBe('Identity Threat')
    const all = await gateway.history.list(code, {})
    expect(all.slice(0, all.length - base).map((h) => [h.category, h.target, h.before, h.after])).toEqual([
      ['other', 'Solution', 'MFA', 'Identity Threat'],
    ])
  })

  // Solution을 비우려 하면 거절하고 값을 유지한다.
  it('refuses to clear the solution and keeps it', async () => {
    // given: Solution이 MFA인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when: 빈 값과 공백만 있는 값으로 수정한다
    await expectApiError(gateway.deals.update(code, { solution: '   ' }), 422, REQUIRED)
    await expectApiError(gateway.deals.update(code, { solution: '' }), 422, REQUIRED)

    // then: 422와 필수 문구이고 Solution은 MFA 그대로다
    expect((await gateway.deals.get(code)).solution).toBe('MFA')
  })

  // Solution을 보내지 않으면 값이 유지된다.
  it('keeps the solution when it is not sent', async () => {
    // given: Solution이 MFA인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: 이름만 바꿔 수정한다
    const updated = await gateway.deals.update(code, { name: '다른 이름' })
    // then: solution이 MFA 그대로다
    expect(updated.solution).toBe('MFA')
  })

  // Vendor만 바꾸면 Solution은 유지되고 이력은 Vendor만 남는다.
  it('changes only the vendor, keeps the solution and records the vendor alone', async () => {
    // given: Silverfort / MFA인 Deal과 현재 이력 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Silverfort / MFA
    const base = (await gateway.history.list(code, {})).length

    // when: Vendor를 Okta로 바꿔 수정한다
    const updated = await gateway.deals.update(code, { vendorId: seedVendorId('Okta') })

    // then: vendor는 Okta, solution은 MFA이고 이력에 Vendor 변경 1건만 남는다
    expect(updated.vendor?.name).toBe('Okta')
    expect(updated.solution).toBe('MFA')
    const all = await gateway.history.list(code, {})
    expect(all.slice(0, all.length - base).map((h) => [h.category, h.target, h.before, h.after])).toEqual([
      ['other', 'Vendor', 'Silverfort', 'Okta'],
    ])
  })

  // Vendor를 비워도 Solution은 유지된다.
  it('clears the vendor and keeps the solution', async () => {
    // given: Silverfort / MFA인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: vendorId를 null로 수정한다
    const updated = await gateway.deals.update(code, { vendorId: null })
    // then: vendor는 null이고 solution은 MFA 그대로다
    expect(updated.vendor).toBeNull()
    expect(updated.solution).toBe('MFA')
  })

  // 같은 Vendor와 공백만 다른 같은 Solution을 다시 보내면 이력이 남지 않는다.
  it('records nothing when the same vendor and the same solution with spaces are sent again', async () => {
    // given: Silverfort / MFA인 Deal과 현재 이력 건수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length

    // when: 같은 Vendor와 공백이 붙은 같은 Solution으로 수정한다
    await gateway.deals.update(code, { vendorId: seedVendorId('Silverfort'), solution: ' MFA ' })

    // then: 이력 건수가 그대로다
    expect((await gateway.history.list(code, {})).length).toBe(base)
  })

  // 대소문자만 바뀐 Solution도 이력에 남긴다.
  it('records a case-only solution change', async () => {
    // given: Solution이 MFA인 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when: Solution을 mfa로 수정한다
    await gateway.deals.update(code, { solution: 'mfa' })

    // then: Solution 이력의 이전·이후 값이 MFA·mfa다
    const entry = (await gateway.history.list(code, {})).find((h) => h.target === 'Solution')
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
