import { describe, expect, it } from 'vitest'
import { CODE, serverHistory, serverUserRef } from '../../../test/fixtures/serverDeal'
import { toHistoryEntry } from './history'
import { USER_ID } from '../../../test/fake/seed/ids'

describe('toHistoryEntry', () => {
  // 서버 이력 항목을 구분·대상·전·후 그대로 매핑한다.
  // 테스트 코드: DD-116
  it('maps the server entry keeping category, target, before and after as they are', () => {
    // given: 서버 이력 항목
    const server = serverHistory({ category: 'expectedClose', target: 'Expected Close', before: '2026-12-31', after: '2027-01-31' })

    // when: 항목으로 바꾼다
    const entry = toHistoryEntry(server)

    // then: id, 시각, 변경자, 구분·대상·전·후가 같다
    expect(entry).toEqual({
      id: 1,
      dealCode: CODE,
      at: '2026-10-15T09:00:00+09:00',
      by: { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' },
      category: 'expectedClose',
      target: 'Expected Close',
      before: '2026-12-31',
      after: '2027-01-31',
    })
  })

  // 등록 항목의 빈 변경 전은 그대로 비어 있다.
  // 테스트 코드: DD-116
  it('keeps an empty before for the creation entry', () => {
    // when: 항목으로 바꾼다 (전제: 구분 created인 서버 항목)
    const entry = toHistoryEntry(serverHistory({ category: 'created', target: 'Deal', before: '', after: 'Deal 등록' }))

    // then: 변경 전이 ''다
    expect(entry).toMatchObject({ category: 'created', before: '', after: 'Deal 등록' })
  })

  // 구분 comment(13번째 값)와 Action Comment 대상 문구를 그대로 둔다.
  // 테스트 코드: DD-116
  it('keeps the comment category and the Action Comment target as they are', () => {
    // when: 항목으로 바꾼다 (전제: 구분 comment인 서버 항목)
    const entry = toHistoryEntry(serverHistory({ category: 'comment', target: 'Action Comment (2026-11-10 미팅)', before: '', after: '등록: 글' }))

    // then: 구분·대상·전후 값이 그대로다
    expect(entry).toMatchObject({ category: 'comment', target: 'Action Comment (2026-11-10 미팅)', before: '', after: '등록: 글' })
  })

  // 퇴사한 변경자는 resigned 상태로 표시한다.
  // 테스트 코드: DD-116
  it('marks a resigned actor', () => {
    // when: 항목으로 바꾼다 (전제: 퇴사한 변경자의 서버 항목)
    const entry = toHistoryEntry(serverHistory({ by: serverUserRef({ id: USER_ID.old, resigned: true }) }))

    // then: 변경자 status가 resigned다
    expect(entry.by.status).toBe('resigned')
  })
})
