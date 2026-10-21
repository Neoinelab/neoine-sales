import { describe, expect, it } from 'vitest'
import { toLabel } from './label'

describe('toLabel', () => {
  it('maps the creator and drops updated_at', () => {
    const label = toLabel({
      id: 1,
      category: 'timeline',
      name: '금년 구매',
      is_default: false,
      created_by: { id: 1, name: '김영업', label: '김영업', resigned: false, role: 'user' },
      created_at: '2026-10-01T09:00:00+09:00',
      updated_at: '2026-10-02T09:00:00+09:00',
      usage_count: 4,
    })

    expect(label).toEqual({
      id: 1,
      category: 'timeline',
      name: '금년 구매',
      isDefault: false,
      createdBy: { id: 1, name: '김영업', role: 'user', status: 'active' },
      createdAt: '2026-10-01T09:00:00+09:00',
      usageCount: 4,
    })
  })
})
