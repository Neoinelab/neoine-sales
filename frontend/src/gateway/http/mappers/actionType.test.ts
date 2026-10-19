import { describe, expect, it } from 'vitest'
import { serverUserRef } from '../../../test/fixtures/serverDeal'
import { toActionType } from './actionType'

describe('toActionType', () => {
  it('maps a default type (no creator) with its usage count and both times', () => {
    expect(
      toActionType({
        id: 'ty-1',
        name: '통화',
        is_default: true,
        created_by: null,
        usage_count: 3,
        created_at: '2026-10-01T09:00:00+09:00',
        updated_at: '2026-10-02T09:00:00+09:00',
      }),
    ).toEqual({
      id: 'ty-1',
      name: '통화',
      isDefault: true,
      createdBy: null,
      usageCount: 3,
      createdAt: '2026-10-01T09:00:00+09:00',
      updatedAt: '2026-10-02T09:00:00+09:00',
    })
  })

  it('maps the creator of a custom type to a user reference', () => {
    const mapped = toActionType({
      id: 'ty-9',
      name: '웨비나',
      is_default: false,
      created_by: serverUserRef({ id: 'u-kim' }),
      usage_count: 0,
      created_at: '2026-10-01T09:00:00+09:00',
      updated_at: '2026-10-01T09:00:00+09:00',
    })

    expect(mapped.createdBy).toMatchObject({ id: 'u-kim', name: '김영업', role: 'sales', status: 'active' })
    expect(mapped.isDefault).toBe(false)
  })
})
