import { describe, expect, it } from 'vitest'
import type { Schemas } from '../../../shared/api/client'
import { serverUserRef } from '../../../test/fixtures/serverDeal'
import { toLicenseContract } from './licenseContract'

function serverContract(over: Partial<Schemas['LicenseContractResponse']> = {}): Schemas['LicenseContractResponse'] {
  return {
    id: 7,
    deal_code: '20261016-A001',
    deal_name: 'ITDR',
    customer: '한빛은행',
    vendor: null,
    product: 'ITDR',
    partner: null,
    sales_owner: serverUserRef(),
    status: 'not_issued',
    license_start: null,
    license_end: null,
    term: null,
    tech_owner: '',
    inspection_cycle: 'none',
    note: '',
    renewed_from_id: null,
    ended_at: null,
    attachment_count: 0,
    deal_is_won: true,
    created_by: serverUserRef(),
    updated_by: serverUserRef(),
    created_at: '2026-10-15T09:00:00+09:00',
    updated_at: '2026-10-15T09:00:00+09:00',
    ...over,
  }
}

describe('toLicenseContract', () => {
  it('maps deal_is_won to dealIsWon for both values', () => {
    expect(toLicenseContract(serverContract({ deal_is_won: true })).dealIsWon).toBe(true)
    expect(toLicenseContract(serverContract({ deal_is_won: false })).dealIsWon).toBe(false)
  })

  it('keeps the other fields mapped', () => {
    expect(toLicenseContract(serverContract())).toMatchObject({ id: 7, dealCode: '20261016-A001', status: 'not_issued', attachmentCount: 0, inspection: 'none' })
  })
})
