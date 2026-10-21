import { describe, expect, it } from 'vitest'
import { serverUserRef } from '../../../test/fixtures/serverDeal'
import { toActionType } from './actionType'
import { USER_ID } from '../../../test/fake/seed/ids'

describe('toActionType', () => {
  it('maps a default type (no creator) with its usage count and both times', () => {
    expect(
      toActionType({
        id: 1,
        name: '통화',
        is_default: true,
        created_by: null,
        usage_count: 3,
        created_at: '2026-10-01T09:00:00+09:00',
        updated_at: '2026-10-02T09:00:00+09:00',
      }),
    ).toEqual({
      id: 1,
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
      id: 9,
      name: '웨비나',
      is_default: false,
      created_by: serverUserRef({ id: USER_ID.kim }),
      usage_count: 0,
      created_at: '2026-10-01T09:00:00+09:00',
      updated_at: '2026-10-01T09:00:00+09:00',
    })

    expect(mapped.createdBy).toMatchObject({ id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' })
    expect(mapped.isDefault).toBe(false)
  })
})
