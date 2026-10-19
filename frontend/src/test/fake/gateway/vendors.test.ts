/** Fake 게이트웨이의 Vendor·Solution 관리가 서버 규칙을 따른다(AC-1~7). 같은 규칙을 HTTP 어댑터는 vendors.contract.ts로 확인한다. */

import { describe, expect, it } from 'vitest'
import { seedSolutionId, seedVendorId } from '../../fixtures/vendors'
import { dealCode, expectApiError, mockAs } from '../testing'

const NO_SUCH_ID = '00000000-0000-4000-8000-000000000000'

describe('vendors.list', () => {
  it('AC-1 sorts vendors and their solutions by lower-case name and carries usage counts', async () => {
    const { gateway } = await mockAs('han')

    const vendors = await gateway.vendors.list()

    expect(vendors.map((v) => v.name)).toEqual([
      'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    const silverfort = vendors.find((v) => v.name === 'Silverfort')
    expect(silverfort).toMatchObject({ id: seedVendorId('Silverfort'), usageCount: 7 })
    expect(silverfort?.solutions.map((s) => [s.name, s.usageCount, s.vendorId])).toEqual([
      ['ITDR', 4, seedVendorId('Silverfort')],
      ['MFA', 3, seedVendorId('Silverfort')],
    ])
  })

  it('requires a login', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.vendors.list(), 401)
  })
})

describe('vendors write', () => {
  it('AC-1 creates a trimmed vendor with zero usage and no solutions', async () => {
    const { gateway } = await mockAs('root')

    const created = await gateway.vendors.create('  Acme  ')

    expect(created).toMatchObject({ name: 'Acme', usageCount: 0, solutions: [] })
    expect((await gateway.vendors.list()).map((v) => v.id)).toContain(created.id)
  })

  it('AC-7 lets only the admin write', async () => {
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      const id = seedVendorId('Splunk')

      await expectApiError(gateway.vendors.create('Acme'), 403)
      await expectApiError(gateway.vendors.rename(id, 'Acme'), 403)
      await expectApiError(gateway.vendors.remove(id), 403)
      await expectApiError(gateway.vendors.createSolution(id, 'X'), 403)
      await expectApiError(gateway.vendors.renameSolution(id, seedSolutionId('Splunk', 'SIEM'), 'X'), 403)
      await expectApiError(gateway.vendors.removeSolution(id, seedSolutionId('Splunk', 'SIEM')), 403)
      expect((await gateway.vendors.list()).find((v) => v.id === id)?.solutions).toHaveLength(2)
    }
  })

  it('AC-4 rejects blank, 101 character and NUL names with the server messages', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.vendors.create('   '), 422, 'Vendor 이름을 입력하세요.')
    await expectApiError(gateway.vendors.create('v'.repeat(101)), 422, 'Vendor 이름은 100자 이내로 입력하세요.')
    await expect(gateway.vendors.create('v'.repeat(100))).resolves.toBeDefined()
    await expectApiError(gateway.vendors.create('a\u0000b'), 422)
    const vendorId = seedVendorId('Splunk')
    await expectApiError(gateway.vendors.createSolution(vendorId, ' '), 422, 'Solution 이름을 입력하세요.')
    await expectApiError(gateway.vendors.createSolution(vendorId, 's'.repeat(201)), 422, 'Solution 이름은 200자 이내로 입력하세요.')
    await expect(gateway.vendors.createSolution(vendorId, 's'.repeat(200))).resolves.toBeDefined()
  })

  it('AC-5 rejects a vendor name that differs only in case, but allows the same solution name under another vendor', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.vendors.create('silverfort'), 409, '이미 있는 Vendor 이름입니다.')
    const silverfort = seedVendorId('Silverfort')
    await expectApiError(gateway.vendors.createSolution(silverfort, 'itdr'), 409, '이 Vendor에 이미 있는 Solution 이름입니다.')
    const other = await gateway.vendors.createSolution(seedVendorId('Okta'), 'ITDR')
    expect(other.name).toBe('ITDR')
  })

  it('AC-5 allows changing only the case of its own name', async () => {
    const { gateway } = await mockAs('root')

    const renamed = await gateway.vendors.rename(seedVendorId('Okta'), 'OKTA')
    const solution = await gateway.vendors.renameSolution(seedVendorId('Okta'), seedSolutionId('Okta', 'SSO'), 'sso')

    expect(renamed.name).toBe('OKTA')
    expect(solution.name).toBe('sso')
  })

  it('AC-2/3 shows a renamed vendor and solution on every deal', async () => {
    const { gateway } = await mockAs('root')
    await gateway.vendors.rename(seedVendorId('Silverfort'), 'Silverfort Inc')
    await gateway.vendors.renameSolution(seedVendorId('Silverfort'), seedSolutionId('Silverfort', 'ITDR'), 'Identity Threat')

    const deal = await gateway.deals.get(dealCode(1))

    expect(deal.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort Inc' })
    expect(deal.solution).toEqual({ id: seedSolutionId('Silverfort', 'ITDR'), name: 'Identity Threat' })
  })

  it('AC-3 treats a solution that is not under the path vendor as missing', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.vendors.renameSolution(seedVendorId('Okta'), seedSolutionId('Silverfort', 'ITDR'), 'X'), 404)
    await expectApiError(gateway.vendors.createSolution(NO_SUCH_ID, 'X'), 404)
  })
})

describe('vendors delete', () => {
  it('AC-6 refuses a used solution and a used vendor with the Deal count and keeps both', async () => {
    const { gateway } = await mockAs('root')
    const silverfort = seedVendorId('Silverfort')

    await expectApiError(
      gateway.vendors.removeSolution(silverfort, seedSolutionId('Silverfort', 'ITDR')),
      409,
      '사용 중인 Solution은 삭제할 수 없습니다. (Deal 4건)',
    )
    await expectApiError(gateway.vendors.remove(silverfort), 409, '사용 중인 Vendor는 삭제할 수 없습니다. (Deal 7건)')
    expect((await gateway.vendors.list()).find((v) => v.id === silverfort)?.solutions).toHaveLength(2)
  })

  it('AC-6 deletes an unused vendor together with its solutions', async () => {
    const { gateway } = await mockAs('root')
    const splunk = seedVendorId('Splunk')

    await gateway.vendors.remove(splunk)

    const vendors = await gateway.vendors.list()
    expect(vendors.map((v) => v.id)).not.toContain(splunk)
    expect(vendors.flatMap((v) => v.solutions.map((s) => s.id))).not.toContain(seedSolutionId('Splunk', 'SIEM'))
    await expectApiError(gateway.vendors.remove(splunk), 404)
  })

  it('AC-6 deletes an unused solution', async () => {
    const { gateway } = await mockAs('root')
    const splunk = seedVendorId('Splunk')

    await gateway.vendors.removeSolution(splunk, seedSolutionId('Splunk', 'SOAR'))

    expect((await gateway.vendors.list()).find((v) => v.id === splunk)?.solutions.map((s) => s.name)).toEqual(['SIEM'])
  })
})
