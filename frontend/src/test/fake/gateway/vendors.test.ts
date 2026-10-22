/** Fake 게이트웨이의 Vendor 관리가 서버 규칙을 따른다(AC-1~4). 같은 규칙을 HTTP 어댑터는 vendors.contract.ts로 확인한다. */

import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import { dealCode, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID } from '../seed/ids'

describe('vendors.list', () => {
  it('AC-1 sorts vendors by lower-case name and carries usage counts without solutions', async () => {
    const { gateway } = await mockAs('han')

    const vendors = await gateway.vendors.list()

    expect(vendors.map((v) => v.name)).toEqual([
      'CrowdStrike', 'CyberArk', 'Okta', 'Palo Alto', 'SentinelOne', 'Silverfort', 'Splunk', 'Tenable', 'Veeam', 'Zscaler',
    ])
    const silverfort = vendors.find((v) => v.name === 'Silverfort')
    expect(silverfort).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort', usageCount: 7 })
    expect(silverfort).not.toHaveProperty('solutions')
  })

  it('requires a login', async () => {
    const { gateway } = await mockAs(null)

    await expectApiError(gateway.vendors.list(), 401)
  })
})

describe('vendors write', () => {
  it('AC-1 creates a trimmed vendor with zero usage', async () => {
    const { gateway } = await mockAs('root')

    const created = await gateway.vendors.create('  Acme  ')

    expect(created).toEqual({ id: created.id, name: 'Acme', usageCount: 0 })
    expect((await gateway.vendors.list()).map((v) => v.id)).toContain(created.id)
  })

  it('AC-2 has no solution management methods', async () => {
    const { gateway } = await mockAs('root')

    for (const method of ['createSolution', 'renameSolution', 'removeSolution']) {
      expect(gateway.vendors).not.toHaveProperty(method)
    }
  })

  it('AC-3 lets only the admin write', async () => {
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      const id = seedVendorId('Splunk')

      await expectApiError(gateway.vendors.create('Acme'), 403)
      await expectApiError(gateway.vendors.rename(id, 'Acme'), 403)
      await expectApiError(gateway.vendors.remove(id), 403)
      expect((await gateway.vendors.list()).map((v) => v.id)).toContain(id)
    }
  })

  it('AC-3 rejects blank, 101 character and NUL names with the server messages', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.vendors.create('   '), 422, 'Vendor 이름을 입력하세요.')
    await expectApiError(gateway.vendors.create('v'.repeat(101)), 422, 'Vendor 이름은 100자 이내로 입력하세요.')
    await expect(gateway.vendors.create('v'.repeat(100))).resolves.toBeDefined()
    await expectApiError(gateway.vendors.create('a\u0000b'), 422)
  })

  it('AC-3 rejects a vendor name that differs only in case', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.vendors.create('silverfort'), 409, '이미 있는 Vendor 이름입니다.')
    await expectApiError(gateway.vendors.rename(seedVendorId('Okta'), 'CYBERARK'), 409, '이미 있는 Vendor 이름입니다.')
  })

  it('AC-3 allows changing only the case of its own name', async () => {
    const { gateway } = await mockAs('root')

    const renamed = await gateway.vendors.rename(seedVendorId('Okta'), 'OKTA')

    expect(renamed.name).toBe('OKTA')
  })

  it('AC-3 shows a renamed vendor on every deal', async () => {
    const { gateway } = await mockAs('root')
    await gateway.vendors.rename(seedVendorId('Silverfort'), 'Silverfort Inc')

    const deal = await gateway.deals.get(dealCode(1))

    expect(deal.vendor).toEqual({ id: seedVendorId('Silverfort'), name: 'Silverfort Inc' })
    expect(deal.solution).toBe('ITDR')
  })

  it('AC-4 treats unknown ids as missing', async () => {
    const { gateway } = await mockAs('root')

    await expectApiError(gateway.vendors.rename(NO_SUCH_ID, 'X'), 404)
    await expectApiError(gateway.vendors.remove(NO_SUCH_ID), 404)
  })
})

describe('vendors delete', () => {
  it('AC-4 refuses a used vendor with the Deal count and keeps it', async () => {
    const { gateway } = await mockAs('root')
    const silverfort = seedVendorId('Silverfort')

    await expectApiError(gateway.vendors.remove(silverfort), 409, '사용 중인 Vendor는 삭제할 수 없습니다. (Deal 7건)')
    expect((await gateway.vendors.list()).map((v) => v.id)).toContain(silverfort)
  })

  it('AC-4 deletes an unused vendor', async () => {
    const { gateway } = await mockAs('root')
    const splunk = seedVendorId('Splunk')

    await gateway.vendors.remove(splunk)

    expect((await gateway.vendors.list()).map((v) => v.id)).not.toContain(splunk)
    await expectApiError(gateway.vendors.remove(splunk), 404)
  })
})
