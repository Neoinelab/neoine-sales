import { describe, expect, it } from 'vitest'
import { serverComment } from '../../../test/fixtures/serverComment'
import { serverUserRef } from '../../../test/fixtures/serverDeal'
import { USER_ID } from '../../../test/fake/seed/ids'
import { toCommentCounts, toDealComment } from './comment'

describe('toDealComment', () => {
  // Deal Comment는 연결 Action이 없고 읽지 않음(readAt null)이며 서버 이름이 화면 이름으로 바뀐다.
  // 테스트 코드: CM-081
  it('maps a deal comment to the screen comment with null action and null readAt', () => {
    // when: Deal Comment 응답을 바꾼다
    const mapped = toDealComment(serverComment())

    // then: 화면 이름의 Comment가 되고 updated_at은 버린다
    expect(mapped).toEqual({
      id: 71,
      dealCode: '20261016-AB12',
      actionId: null,
      action: null,
      body: '예산 회의 예정',
      author: { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' },
      createdAt: '2026-11-12T09:30:00+09:00',
      readAt: null,
    })
  })

  // Action Comment는 연결 Action 요약(수행일·진행사항·Next Action)과 읽음 시각을 가진다.
  // 테스트 코드: CM-081
  it('maps the linked action summary (action becomes progress) and the read time', () => {
    // when: Action에 연결되고 읽은 Comment를 바꾼다
    const mapped = toDealComment(
      serverComment({
        action_id: 41,
        action: { id: 41, acted_on: '2026-11-10', action: '킥오프 미팅', next_action: null },
        read_at: '2026-11-13T10:00:00+09:00',
      }),
    )

    // then: 요약이 {id, actedOn, progress, nextAction}이고 readAt이 채워진다
    expect(mapped).toMatchObject({
      actionId: 41,
      action: { id: 41, actedOn: '2026-11-10', progress: '킥오프 미팅', nextAction: null },
      readAt: '2026-11-13T10:00:00+09:00',
    })
  })

  // 퇴사한 작성자는 resigned 상태로 표기된다.
  // 테스트 코드: CM-081
  it('marks a resigned author', () => {
    // when: 퇴사자가 쓴 Comment를 바꾼다
    const mapped = toDealComment(serverComment({ author: serverUserRef({ id: USER_ID.old, resigned: true }) }))

    // then: 작성자 상태가 resigned다
    expect(mapped.author).toMatchObject({ id: USER_ID.old, status: 'resigned' })
  })

  // 본문은 줄바꿈 그대로 길이를 자르지 않는다.
  // 테스트 코드: CM-081
  it('keeps line breaks and does not cut a long body', () => {
    // given: 줄바꿈이 있는 20,000자 본문
    const body = `자료 전달\n${'가'.repeat(20000)}`

    // when: 바꾼다
    const mapped = toDealComment(serverComment({ body }))

    // then: 그대로다
    expect(mapped.body).toBe(body)
  })
})

describe('toCommentCounts', () => {
  // 읽지 않은 수의 by_action 배열은 action id를 키로 한 객체가 된다.
  // 테스트 코드: CM-081
  it('maps by_action to a record keyed by action id', () => {
    // when: 집계 응답을 바꾼다
    const mapped = toCommentCounts({ unread: 3, by_action: [{ action_id: 41, unread: 2 }, { action_id: 42, unread: 1 }] })

    // then: {unread, byAction}이다
    expect(mapped).toEqual({ unread: 3, byAction: { 41: 2, 42: 1 } })
  })

  // 읽지 않은 것이 없으면 byAction은 빈 객체다.
  // 테스트 코드: CM-081
  it('gives an empty record when nothing is unread', () => {
    // when·then: 0건 응답은 빈 byAction이다
    expect(toCommentCounts({ unread: 0, by_action: [] })).toEqual({ unread: 0, byAction: {} })
  })
})
