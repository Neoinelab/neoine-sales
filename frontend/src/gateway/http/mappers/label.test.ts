import { describe, expect, it } from 'vitest'
import { toLabel } from './label'

describe('toLabel', () => {
  // Label 응답은 만든 사람을 사용자 참조로 바꾸고 수정 시각은 버린다.
  // 테스트 코드: CL-092
  it('maps the creator and drops updated_at', () => {
    // when: 화면 값으로 바꾼다 (전제: 만든 사람이 있는 Label 응답)
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

    // then: 만든 사람·사용 수·만든 시각만 담긴다
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
