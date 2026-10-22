import { describe, expect, it } from 'vitest'
import { toVendor } from './vendor'

describe('toVendor', () => {
  it('maps the usage count and drops the timestamps', () => {
    const vendor = toVendor({
      id: 1,
      name: 'Silverfort',
      usage_count: 5,
      created_at: '2026-10-01T09:00:00+09:00',
      updated_at: '2026-10-02T09:00:00+09:00',
    })

    expect(vendor).toEqual({ id: 1, name: 'Silverfort', usageCount: 5 })
  })

  it('has no solution list', () => {
    const vendor = toVendor({ id: 9, name: 'Veeam', usage_count: 0, created_at: 'x', updated_at: 'x' })

    expect(vendor).not.toHaveProperty('solutions')
  })
})
