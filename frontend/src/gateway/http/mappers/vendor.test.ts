import { describe, expect, it } from 'vitest'
import { toSolution, toVendor } from './vendor'

const solution = (over: Record<string, unknown> = {}) => ({
  id: 'sl-1',
  vendor_id: 'vd-1',
  name: 'ITDR',
  usage_count: 2,
  created_at: '2026-10-01T09:00:00+09:00',
  updated_at: '2026-10-02T09:00:00+09:00',
  ...over,
})

describe('toSolution', () => {
  it('maps snake_case to camelCase and drops the timestamps', () => {
    expect(toSolution(solution())).toEqual({ id: 'sl-1', vendorId: 'vd-1', name: 'ITDR', usageCount: 2 })
  })
})

describe('toVendor', () => {
  it('maps the usage count and nests the solutions in the server order', () => {
    const vendor = toVendor({
      id: 'vd-1',
      name: 'Silverfort',
      usage_count: 5,
      created_at: '2026-10-01T09:00:00+09:00',
      updated_at: '2026-10-02T09:00:00+09:00',
      solutions: [solution(), solution({ id: 'sl-2', name: 'MFA', usage_count: 0 })],
    })

    expect(vendor).toEqual({
      id: 'vd-1',
      name: 'Silverfort',
      usageCount: 5,
      solutions: [
        { id: 'sl-1', vendorId: 'vd-1', name: 'ITDR', usageCount: 2 },
        { id: 'sl-2', vendorId: 'vd-1', name: 'MFA', usageCount: 0 },
      ],
    })
  })

  it('keeps a vendor without solutions', () => {
    const vendor = toVendor({ id: 'vd-9', name: 'Veeam', usage_count: 0, created_at: 'x', updated_at: 'x', solutions: [] })

    expect(vendor.solutions).toEqual([])
  })
})
