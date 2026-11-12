import { describe, expect, it } from 'vitest'
import { serverUserRef } from '../../../test/fixtures/serverDeal'
import { toActionType } from './actionType'
import { USER_ID } from '../../../test/fake/seed/ids'

describe('toActionType', () => {
  // 기본 유형(만든 사람 없음)은 사용 수와 두 시각과 함께 바뀐다.
  // 테스트 코드: CL-092
  it('maps a default type (no creator) with its usage count and both times', () => {
    // when: 기본 유형 응답을 화면 값으로 바꾼다
    const mapped = toActionType({
      id: 1,
      name: '통화',
      is_default: true,
      created_by: null,
      usage_count: 3,
      created_at: '2026-10-01T09:00:00+09:00',
      updated_at: '2026-10-02T09:00:00+09:00',
    })

    // then: createdBy가 null이고 사용 수·두 시각이 담긴다
    expect(mapped).toEqual({
      id: 1,
      name: '통화',
      isDefault: true,
      createdBy: null,
      usageCount: 3,
      createdAt: '2026-10-01T09:00:00+09:00',
      updatedAt: '2026-10-02T09:00:00+09:00',
    })
  })

  // 직접 만든 유형의 만든 사람은 사용자 참조로 바뀐다.
  // 테스트 코드: CL-092
  it('maps the creator of a custom type to a user reference', () => {
    // when: 만든 사람이 있는 유형 응답을 바꾼다
    const mapped = toActionType({
      id: 9,
      name: '웨비나',
      is_default: false,
      created_by: serverUserRef({ id: USER_ID.kim }),
      usage_count: 0,
      created_at: '2026-10-01T09:00:00+09:00',
      updated_at: '2026-10-01T09:00:00+09:00',
    })

    // then: createdBy가 사용자 참조이고 기본이 아니다
    expect(mapped.createdBy).toMatchObject({ id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' })
    expect(mapped.isDefault).toBe(false)
  })
})
