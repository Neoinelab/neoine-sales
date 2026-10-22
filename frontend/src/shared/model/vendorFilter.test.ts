import { describe, expect, it } from 'vitest'
import { effectiveVendorFilter } from './vendorFilter'
import type { Vendor } from './types'

const vendors: Vendor[] = [
  { id: 1, name: 'Okta', usageCount: 3 },
  { id: 2, name: 'Silverfort', usageCount: 7 },
]

describe('effectiveVendorFilter', () => {
  it('keeps a registered vendor id', () => {
    expect(effectiveVendorFilter(vendors, 2)).toEqual({ vendorId: 2 })
  })

  it('drops an unknown vendor id', () => {
    expect(effectiveVendorFilter(vendors, 99)).toEqual({ vendorId: undefined })
  })

  it('leaves an unset vendor unset', () => {
    expect(effectiveVendorFilter(vendors, undefined)).toEqual({ vendorId: undefined })
  })

  it('does not judge before the list is known (loading or failed)', () => {
    expect(effectiveVendorFilter(undefined, 99)).toEqual({ vendorId: 99 })
  })

  it('never carries a solution', () => {
    expect(Object.keys(effectiveVendorFilter(vendors, 1))).not.toContain('solutionId')
  })
})
