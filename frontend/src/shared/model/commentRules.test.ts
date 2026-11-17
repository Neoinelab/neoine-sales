import { describe, expect, it } from 'vitest'
import { USER_ID } from '../../test/fake/seed/ids'
import { badgeText } from './commentBadge'
import { canDeleteComment, canMarkCommentsRead } from './permissions'

describe('badgeText', () => {
  // 0이면 배지가 없고 1~99는 숫자 그대로, 100 이상은 "99+"다.
  // 테스트 코드: CM-083
  it.each([
    [0, null],
    [1, '1'],
    [99, '99'],
    [100, '99+'],
    [250, '99+'],
  ])('gives %s as %s', (count, expected) => {
    // when: 배지 함수에 건수를 넣는다
    const text = badgeText(count)

    // then: 정해진 표기(0은 배지 없음)다
    expect(text).toBe(expected)
  })
})

describe('canDeleteComment', () => {
  // admin은 모든 Comment, sales는 본인 Comment만, user는 자기 것이어도 못 지운다.
  // 테스트 코드: CM-083
  it.each([
    ['sales 본인', { id: USER_ID.kim, role: 'sales' }, USER_ID.kim, true],
    ['sales 남의 것', { id: USER_ID.kim, role: 'sales' }, USER_ID.park, false],
    ['admin 남의 것', { id: USER_ID.root, role: 'admin' }, USER_ID.park, true],
    ['user 본인', { id: USER_ID.lee, role: 'user' }, USER_ID.lee, false],
  ] as const)('%s → %s', (_label, viewer, authorId, expected) => {
    // when: 삭제 판정에 (보는 사람, 작성자)를 넣는다
    const allowed = canDeleteComment(viewer, authorId)

    // then: 정해진 결과다
    expect(allowed).toBe(expected)
  })
})

describe('canMarkCommentsRead', () => {
  // 읽음 처리는 그 Deal의 Owner 본인만 한다(admin도 Owner가 아니면 못 한다).
  // 테스트 코드: CM-083
  it.each([
    ['Owner 본인', { id: USER_ID.kim, role: 'sales' }, USER_ID.kim, true],
    ['admin(Owner 아님)', { id: USER_ID.root, role: 'admin' }, USER_ID.kim, false],
    ['다른 sales', { id: USER_ID.park, role: 'sales' }, USER_ID.kim, false],
  ] as const)('%s → %s', (_label, viewer, ownerId, expected) => {
    // when: 읽음 처리 판정에 (보는 사람, Owner)를 넣는다
    const allowed = canMarkCommentsRead(viewer, ownerId)

    // then: 정해진 결과다
    expect(allowed).toBe(expected)
  })
})
