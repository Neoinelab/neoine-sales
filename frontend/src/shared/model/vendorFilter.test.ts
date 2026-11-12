import { describe, expect, it } from 'vitest'
import { effectiveVendorFilter } from './vendorFilter'
import type { Vendor } from './types'

const vendors: Vendor[] = [
  { id: 1, name: 'Okta', usageCount: 3 },
  { id: 2, name: 'Silverfort', usageCount: 7 },
]

describe('effectiveVendorFilter', () => {
  it('등록된 Vendor id는 유지한다', () => {
    // when: 등록된 id로 유효 Vendor 필터를 구한다
    const result = effectiveVendorFilter(vendors, 2)

    // then: 그 id를 유지한다
    expect(result).toEqual({ vendorId: 2 })
  })

  it('모르는 Vendor id는 버린다', () => {
    // when: 목록에 없는 id로 유효 Vendor 필터를 구한다
    const result = effectiveVendorFilter(vendors, 99)

    // then: vendorId가 undefined다
    expect(result).toEqual({ vendorId: undefined })
  })

  it('고르지 않은 Vendor는 그대로 비워 둔다', () => {
    // when: id 없이 유효 Vendor 필터를 구한다
    const result = effectiveVendorFilter(vendors, undefined)

    // then: vendorId가 undefined다
    expect(result).toEqual({ vendorId: undefined })
  })

  it('목록을 모르는 동안(불러오는 중·실패)에는 판정하지 않고 그대로 둔다', () => {
    // when: 목록 없이 유효 Vendor 필터를 구한다
    const result = effectiveVendorFilter(undefined, 99)

    // then: 입력한 id를 그대로 돌려준다
    expect(result).toEqual({ vendorId: 99 })
  })

  it('Solution 값은 싣지 않는다', () => {
    // when: 유효 Vendor 필터를 구한다
    const result = Object.keys(effectiveVendorFilter(vendors, 1))

    // then: solutionId 키가 없다
    expect(result).not.toContain('solutionId')
  })
})
