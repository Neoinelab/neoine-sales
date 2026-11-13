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
    ended_on: null,
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
  // 응답의 deal_is_won을 dealIsWon으로 옮긴다(true·false 모두).
  // 테스트 코드: LC-028
  it('maps deal_is_won to dealIsWon for both values', () => {
    // when: toLicenseContract로 변환한다 (전제: 서버 응답 JSON)
    const actual1 = toLicenseContract(serverContract({ deal_is_won: true })).dealIsWon
    const actual2 = toLicenseContract(serverContract({ deal_is_won: false })).dealIsWon

    // then: dealIsWon이 입력과 같다
    expect(actual1).toBe(true)
    expect(actual2).toBe(false)
  })

  // 나머지 필드도 화면 모델로 그대로 옮긴다.
  it('keeps the other fields mapped', () => {
    // when: toLicenseContract로 변환한다 (전제: 서버 응답 JSON)
    const actual = toLicenseContract(serverContract())

    // then: 필드가 화면 모델 이름으로 옮겨진다
    expect(actual).toMatchObject({ id: 7, dealCode: '20261016-A001', status: 'not_issued', attachmentCount: 0, inspection: 'none' })
  })
})
