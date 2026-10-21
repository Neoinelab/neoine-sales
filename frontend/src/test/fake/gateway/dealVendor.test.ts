/** Deal 등록·수정이 Vendor·Solution을 id로 받고 서버 검증 문구·History를 따른다(AC-9~14). */

import { describe, expect, it } from 'vitest'
import { seedSolutionId, seedVendorId } from '../../fixtures/vendors'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'


const NEEDS_VENDOR = 'Solution을 선택하려면 Vendor를 먼저 선택하세요.'
const UNKNOWN_VENDOR = '선택한 Vendor가 없습니다. 목록에서 다시 선택하세요.'
const MISMATCH = '선택한 Solution은 이 Vendor에 속하지 않습니다.'

describe('deals.create vendor and solution', () => {
  it('AC-13 returns vendor and solution as {id, name}', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput(USER_ID.kim))

    expect(created.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort' })
    expect(created.solution).toEqual({ id: seedSolutionId('Silverfort', 'ITDR'), name: 'ITDR' })
  })

  it('AC-9 accepts no vendor and no solution as null', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput(USER_ID.kim, { vendorId: null, solutionId: null }))

    expect(created.vendor).toBeNull()
    expect(created.solution).toBeNull()
  })

  it('AC-9 accepts a vendor without a solution', async () => {
    const { gateway } = await mockAs('kim')

    const created = await gateway.deals.create(dealInput(USER_ID.kim, { vendorId: seedVendorId('Okta'), solutionId: null }))

    expect(created.vendor?.name).toBe('Okta')
    expect(created.solution).toBeNull()
  })

  it('AC-12 rejects the three invalid choices with the server messages', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { vendorId: null, solutionId: seedSolutionId('Okta', 'SSO') })), 422, NEEDS_VENDOR)
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { vendorId: NO_SUCH_ID, solutionId: null })), 422, UNKNOWN_VENDOR)
    await expectApiError(
      gateway.deals.create(dealInput(USER_ID.kim, { vendorId: seedVendorId('Okta'), solutionId: seedSolutionId('Silverfort', 'ITDR') })),
      422,
      MISMATCH,
    )
  })

  it('AC-12 checks the vendor after the Deal Name and before the Owner', async () => {
    const { gateway } = await mockAs('kim')

    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { name: ' ', vendorId: NO_SUCH_ID })), 422, 'Deal Name을 입력하세요.')
    await expectApiError(gateway.deals.create(dealInput(USER_ID.root, { vendorId: NO_SUCH_ID })), 422, UNKNOWN_VENDOR)
  })
})

describe('deals.update vendor and solution', () => {
  it('AC-12 refuses a vendor change alone while the solution belongs to the old vendor', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Silverfort / MFA

    await expectApiError(gateway.deals.update(code, { vendorId: seedVendorId('Okta') }), 422, MISMATCH)

    expect((await gateway.deals.get(code)).vendor?.name).toBe('Silverfort')
  })

  it('AC-10/14 changes the vendor with a null solution and records both with names', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Silverfort / MFA
    const base = (await gateway.history.list(code, {})).length

    const updated = await gateway.deals.update(code, { vendorId: seedVendorId('Okta'), solutionId: null })

    expect(updated.vendor?.name).toBe('Okta')
    expect(updated.solution).toBeNull()
    const added = (await gateway.history.list(code, {})).slice(0, (await gateway.history.list(code, {})).length - base)
    expect(added.map((h) => [h.category, h.target, h.before, h.after]).sort()).toEqual([
      ['other', 'Solution', 'MFA', '선택 안 함'],
      ['other', 'Vendor', 'Silverfort', 'Okta'],
    ])
  })

  it('AC-14 records nothing when the same vendor and solution are sent again', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length

    await gateway.deals.update(code, { vendorId: seedVendorId('Silverfort'), solutionId: seedSolutionId('Silverfort', 'MFA') })

    expect((await gateway.history.list(code, {})).length).toBe(base)
  })

  it('AC-14 keeps old history entries when a vendor is renamed', async () => {
    const admin = await mockAs('root')
    const code = dealCode(2)
    await admin.gateway.deals.update(code, { vendorId: seedVendorId('Okta'), solutionId: null })
    await admin.gateway.vendors.rename(seedVendorId('Okta'), 'Okta Inc')

    const entry = (await admin.gateway.history.list(code, {})).find((h) => h.target === 'Vendor')

    expect(entry?.after).toBe('Okta')
  })
})
