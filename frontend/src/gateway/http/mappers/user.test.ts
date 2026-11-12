import { describe, expect, it } from 'vitest'
import { toMe, toUserRef } from './user'

describe('toMe', () => {
  // 서버 사용자 응답의 user_id·subject를 화면 값의 id·loginId로 바꾼다.
  it('renames user_id and subject', () => {
    // given: user_id·subject를 쓰는 서버 응답
    const server = { user_id: 1, subject: 'root', name: '최관리', role: 'admin', email: null } as const

    // when: 화면 값으로 바꾼다
    const me = toMe(server)

    // then: user_id는 id, subject는 loginId이고 이름·역할이 같다
    expect(me).toEqual({
      id: 1,
      loginId: 'root',
      name: '최관리',
      role: 'admin',
    })
  })
})

describe('toUserRef', () => {
  // 퇴사 참조는 상태만 resigned로 바꾸고 이름은 그대로 둔다
  // 테스트 코드: US-110
  it('marks a resigned user, keeping the plain name (the screens add the suffix)', () => {
    // when: 화면 값으로 바꾼다 (전제: 퇴사 UserRef 응답)
    const actual = toUserRef({ id: 9, name: '강퇴사', label: '강퇴사(퇴사)', resigned: true, role: 'sales' })

    // then: 이름은 그대로이고 상태가 resigned다
    expect(actual).toMatchObject({ name: '강퇴사', status: 'resigned' })
  })

  // 재직 참조는 상태가 active다
  // 테스트 코드: US-110
  it('marks an active user', () => {
    // when: 화면 값으로 바꾼다 (전제: 재직 UserRef 응답)
    const actual = toUserRef({ id: 1, name: '최관리', label: '최관리', resigned: false, role: 'admin' })

    // then: 상태가 active다
    expect(actual).toMatchObject({ status: 'active' })
  })

  // UserRef의 역할은 서버 값을 그대로 쓴다
  // 테스트 코드: US-110
  it.each(['admin', 'sales', 'user'] as const)('uses the server role %s as is (no placeholder)', (role) => {
    // given: 역할별 UserRef 응답
    const server = { id: 1, name: '이름', label: '이름', resigned: false, role }

    // when: 화면 값으로 바꾼다
    const ref = toUserRef(server)

    // then: 역할이 서버 값 그대로다
    expect(ref).toEqual({
      id: 1,
      name: '이름',
      role,
      status: 'active',
    })
  })

  // 퇴사자의 참조도 서버 역할을 그대로 쓴다
  // 테스트 코드: US-110
  it('keeps the role of a resigned user', () => {
    // when: 화면 값으로 바꾼다 (전제: 퇴사 sales UserRef 응답)
    const actual = toUserRef({ id: 9, name: '강퇴사', label: '강퇴사(퇴사)', resigned: true, role: 'sales' }).role

    // then: 역할이 sales다
    expect(actual).toBe('sales')
  })
})
