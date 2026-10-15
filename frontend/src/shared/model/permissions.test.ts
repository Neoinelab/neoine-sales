import { describe, expect, it } from 'vitest'
import { canBeOwner, canDeleteAttachment, canDeleteDeal, canWrite, visibleMenu } from './permissions'

const resigned = { id: 'u-old', name: '강퇴사', role: 'sales', status: 'resigned' } as const
const active = { id: 'u-park', name: '박영업', role: 'sales', status: 'active' } as const

describe('permissions', () => {
  it('쓰기와 메뉴', () => {
    expect(canWrite('user')).toBe(false)
    expect(canWrite('sales')).toBe(true)
    expect(visibleMenu('admin')).toHaveLength(5)
    expect(visibleMenu('sales')).toHaveLength(4)
  })

  it('Deal 삭제: admin 전체, sales 본인, user 불가', () => {
    expect(canDeleteDeal({ id: 'u-root', role: 'admin' }, 'u-kim')).toBe(true)
    expect(canDeleteDeal({ id: 'u-kim', role: 'sales' }, 'u-kim')).toBe(true)
    expect(canDeleteDeal({ id: 'u-park', role: 'sales' }, 'u-kim')).toBe(false)
    expect(canDeleteDeal({ id: 'u-han', role: 'user' }, 'u-han')).toBe(false)
  })

  it('T-FILE-06 파일 삭제 권한 표', () => {
    expect(canDeleteAttachment({ id: 'u-root', role: 'admin' }, active)).toBe(true)
    expect(canDeleteAttachment({ id: 'u-park', role: 'sales' }, active)).toBe(true)
    expect(canDeleteAttachment({ id: 'u-kim', role: 'sales' }, active)).toBe(false)
    expect(canDeleteAttachment({ id: 'u-kim', role: 'sales' }, resigned)).toBe(true)
    expect(canDeleteAttachment({ id: 'u-han', role: 'user' }, resigned)).toBe(false)
  })

  it('Owner 후보는 재직 sales뿐', () => {
    expect(canBeOwner(active)).toBe(true)
    expect(canBeOwner(resigned)).toBe(false)
    expect(canBeOwner({ role: 'admin', status: 'active' })).toBe(false)
  })
})
