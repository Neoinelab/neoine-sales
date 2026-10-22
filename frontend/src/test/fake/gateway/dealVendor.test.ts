/** Deal 등록·수정이 Vendor는 id로, Solution은 필수 자유 텍스트로 받고 서버 검증 문구·History를 따른다(AC-6~13). */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const UNKNOWN_VENDOR = '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.'
const REQUIRED = 'Solution을 입력하세요.'
const TOO_LONG = 'Solution은 200자 이내로 입력하세요.'

describe('deals.create vendor and solution', () => {
  it('AC-6 returns the vendor as {id, name} and the solution as a trimmed string', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput(USER_ID.kim, { solution: '  ITDR  ' }))

    expect(created.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(created.solution).toBe('ITDR')
  })

  it('AC-8 accepts a solution without a vendor', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput(USER_ID.kim, { vendorId: null, solution: 'ITDR' }))

    expect(created.vendor).toBeNull()
    expect(created.solution).toBe('ITDR')
  })

  it('requires a non-blank solution', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { solution: '' })), 422, REQUIRED)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { solution: '   ' })), 422, REQUIRED)
  })

  it('AC-7 accepts 200 characters and rejects 201 and NUL', async () => {
    const { gateway } = await mockAs('kim')

    await expect(gateway.deals.create(dealInput(USER_ID.kim, { solution: 'a'.repeat(200) }))).resolves.toBeDefined()
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { solution: 'a'.repeat(201) })), 422, TOO_LONG)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { solution: 'a\u0000b' })), 422)
  })

  it('AC-7 checks the vendor after the Deal Name, the solution after the vendor and the owner after the solution', async () => {
    const { gateway } = await mockAs('kim')
    const tooLong = 'a'.repeat(201)

    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { name: ' ', vendorId: NO_SUCH_ID, solution: tooLong })), 422, 'Deal Name을 입력하세요.')
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { vendorId: NO_SUCH_ID, solution: tooLong })), 422, UNKNOWN_VENDOR)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.root, { solution: tooLong })), 422, TOO_LONG)
  })
})

describe('deals.update vendor and solution', () => {
  it('AC-9 replaces the solution text, trims it and records it as text in the history', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Silverfort / MFA
    const base = (await gateway.history.list(code, {})).length

    const updated = await gateway.deals.update(code, { solution: '  Identity Threat ' })

    expect(updated.solution).toBe('Identity Threat')
    const all = await gateway.history.list(code, {})
    expect(all.slice(0, all.length - base).map((h) => [h.category, h.target, h.before, h.after])).toEqual([
      ['other', 'Solution', 'MFA', 'Identity Threat'],
    ])
  })

  it('AC-9 refuses to clear the solution and keeps it', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    await expectApiError(gateway.deals.update(code, { solution: '   ' }), 422, REQUIRED)
    await expectApiError(gateway.deals.update(code, { solution: '' }), 422, REQUIRED)

    expect((await gateway.deals.get(code)).solution).toBe('MFA')
  })

  it('AC-9 keeps the solution when it is not sent', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    const updated = await gateway.deals.update(code, { name: '다른 이름' })

    expect(updated.solution).toBe('MFA')
  })

  it('AC-9/11 changes only the vendor, keeps the solution and records the vendor alone', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Silverfort / MFA
    const base = (await gateway.history.list(code, {})).length

    const updated = await gateway.deals.update(code, { vendorId: seedVendorId('Okta') })

    expect(updated.vendor?.name).toBe('Okta')
    expect(updated.solution).toBe('MFA')
    const all = await gateway.history.list(code, {})
    expect(all.slice(0, all.length - base).map((h) => [h.category, h.target, h.before, h.after])).toEqual([
      ['other', 'Vendor', 'Silverfort', 'Okta'],
    ])
  })

  it('AC-9 clears the vendor and keeps the solution', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    const updated = await gateway.deals.update(code, { vendorId: null })

    expect(updated.vendor).toBeNull()
    expect(updated.solution).toBe('MFA')
  })

  it('AC-11 records nothing when the same vendor and the same solution with spaces are sent again', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length

    await gateway.deals.update(code, { vendorId: seedVendorId('Silverfort'), solution: ' MFA ' })

    expect((await gateway.history.list(code, {})).length).toBe(base)
  })

  it('AC-11 records a case-only solution change', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    await gateway.deals.update(code, { solution: 'mfa' })

    const entry = (await gateway.history.list(code, {})).find((h) => h.target === 'Solution')
    expect([entry?.before, entry?.after]).toEqual(['MFA', 'mfa'])
  })

  it('AC-11 keeps old history entries when a vendor is renamed', async () => {
    const admin = await mockAs('root')
    const code = dealCode(2)
    await admin.gateway.deals.update(code, { vendorId: seedVendorId('Okta') })
    await admin.gateway.vendors.rename(seedVendorId('Okta'), 'Okta Inc')

    const entry = (await admin.gateway.history.list(code, {})).find((h) => h.target === 'Vendor')

    expect(entry?.after).toBe('Okta')
  })
})
