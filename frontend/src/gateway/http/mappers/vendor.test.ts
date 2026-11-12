import { describe, expect, it } from 'vitest'
import { toVendor } from './vendor'

describe('toVendor', () => {
  // Vendor 응답은 사용 수를 담고 시각은 버린다.
  // 테스트 코드: CL-092
  it('maps the usage count and drops the timestamps', () => {
    // when: Vendor 응답을 화면 값으로 바꾼다
    const vendor = toVendor({
      id: 1,
      name: 'Silverfort',
      usage_count: 5,
      created_at: '2026-10-01T09:00:00+09:00',
      updated_at: '2026-10-02T09:00:00+09:00',
    })

    // then: {id, name, usageCount}만 담긴다
    expect(vendor).toEqual({ id: 1, name: 'Silverfort', usageCount: 5 })
  })

  // 바뀐 Vendor에는 Solution 목록이 없다.
  // 테스트 코드: CL-092
  it('has no solution list', () => {
    // when: Vendor 응답을 화면 값으로 바꾼다
    const vendor = toVendor({ id: 9, name: 'Veeam', usage_count: 0, created_at: 'x', updated_at: 'x' })

    // then: solutions 속성이 없다
    expect(vendor).not.toHaveProperty('solutions')
  })
})
