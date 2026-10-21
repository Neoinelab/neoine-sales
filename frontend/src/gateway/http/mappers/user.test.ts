import { describe, expect, it } from 'vitest'
import { toMe, toUserRef } from './user'

describe('toMe', () => {
  it('renames user_id and subject', () => {
    expect(toMe({ user_id: 1, subject: 'root', name: '최관리', role: 'admin', email: null })).toEqual({
      id: 1,
      loginId: 'root',
      name: '최관리',
      role: 'admin',
    })
  })
})

describe('toUserRef', () => {
  it('marks a resigned user, keeping the plain name (the screens add the suffix)', () => {
    expect(toUserRef({ id: 9, name: '강퇴사', label: '강퇴사(퇴사)', resigned: true, role: 'sales' })).toMatchObject({ name: '강퇴사', status: 'resigned' })
  })

  it('marks an active user', () => {
    expect(toUserRef({ id: 1, name: '최관리', label: '최관리', resigned: false, role: 'admin' })).toMatchObject({ status: 'active' })
  })

  it.each(['admin', 'sales', 'user'] as const)('uses the server role %s as is (no placeholder)', (role) => {
    expect(toUserRef({ id: 1, name: '이름', label: '이름', resigned: false, role })).toEqual({
      id: 1,
      name: '이름',
      role,
      status: 'active',
    })
  })

  it('keeps the role of a resigned user', () => {
    expect(toUserRef({ id: 9, name: '강퇴사', label: '강퇴사(퇴사)', resigned: true, role: 'sales' }).role).toBe('sales')
  })
})
