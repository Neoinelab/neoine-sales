import { describe, expect, it } from 'vitest'
import type { ActionInput } from '../../../shared/model/types'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'
import { dealCode, expectApiError, mockAs } from '../testing'

/** Fake Comment 게이트웨이가 서버(CM-R1~R29)와 같은 규칙·문구·판정 순서를 따르는지 본다. 김영업이 시드 Deal 2(code)의 Owner다. */
const action = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-12-01',
  comment: '',
  ...over,
})

async function ownerOf(code: string): Promise<number> {
  const { gateway } = await mockAs('root')
  return (await gateway.deals.get(code)).ownerId
}

describe('comments 작성', () => {
  // 작성자·시각은 서버가 정하고 Owner가 쓰면 읽음, 다른 사람이 쓰면 읽지 않음이며 이력 "등록: <본문>"이 남는다.
  // 테스트 코드: CM-082
  it('writes as the requester, read for the owner and unread for others, with a history line', async () => {
    // given: Deal 2의 Owner
    const code = dealCode(2)
    const ownerId = await ownerOf(code)
    const mock = await mockAs(ownerId === USER_ID.kim ? 'kim' : 'park')

    // when: Owner가 쓰고, admin이 쓴다
    const mine = await mock.gateway.comments.create(code, { body: ' 내 글 ' })
    await mock.signInAs(USER_ID.root)
    const theirs = await mock.gateway.comments.create(code, { body: '남의 글' })

    // then: 작성자는 요청자이고 Owner 글만 읽음이며 이력 맨 위는 admin의 등록 줄이다
    expect(mine).toMatchObject({ body: '내 글', author: { id: ownerId }, actionId: null, action: null })
    expect(mine.readAt).not.toBeNull()
    expect(theirs).toMatchObject({ author: { id: USER_ID.root }, readAt: null })
    expect((await mock.gateway.history.list(code, {}))[0]).toMatchObject({ category: 'comment', target: 'Comment', before: '', after: '등록: 남의 글', by: { id: USER_ID.root } })
  })

  // 판정 순서: user 403 → 없는 Deal 404가 본문 오류보다 먼저 → NUL → 빈 값 → 연결 Action.
  // 테스트 코드: CM-082
  it('judges in the server order: read-only 403, missing deal 404, NUL, blank, then the action', async () => {
    // given: sales와 user
    const code = dealCode(2)
    const sales = await mockAs('kim')
    const user = await mockAs('han')
    // when·then: user는 없는 Deal이어도 읽기 전용 403
    await expectApiError(user.gateway.comments.create('20000101-ZZZZ', { body: 'x' }), 403, '이 작업을 할 권한이 없습니다(읽기 전용 계정)')
    // when·then: 없는 Deal·형식이 틀린 code는 본문이 잘못돼도 404가 먼저
    await expectApiError(sales.gateway.comments.create('20000101-ZZZZ', { body: '' }), 404, 'Deal을 찾을 수 없습니다.')
    await expectApiError(sales.gateway.comments.create('bad', { body: '' }), 404, 'Deal을 찾을 수 없습니다.')
    // when·then: NUL이 빈 값 판정보다 먼저이고(NUL만 있는 본문), 빈 값은 문구가 다르다
    await expectApiError(sales.gateway.comments.create(code, { body: '\u0000' }), 422, 'Comment에는 NUL 문자를 쓸 수 없습니다')
    await expectApiError(sales.gateway.comments.create(code, { body: ' \n ' }), 422, 'Comment를 입력하세요.')
    // when·then: 연결 Action은 본문 검사 다음에 판정한다
    await expectApiError(sales.gateway.comments.create(code, { body: '', actionId: NO_SUCH_ID }), 422, 'Comment를 입력하세요.')
    await expectApiError(sales.gateway.comments.create(code, { body: 'x', actionId: NO_SUCH_ID }), 422, '선택한 Action이 이 Deal에 없습니다.')
    // then: 아무것도 저장되지 않는다
    expect(await sales.gateway.comments.list(code)).toEqual([])
  })

  // 긴 본문(20,000자)과 안쪽 줄바꿈은 그대로 저장하고 이력에서만 잘린다.
  // 테스트 코드: CM-082
  it('keeps a 20,000 character body and its line breaks whole while the history is clipped', async () => {
    // given: 긴 본문
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const body = `줄1\n${'가'.repeat(20000)}`

    // when: 쓴다
    const created = await gateway.comments.create(code, { body })

    // then: 본문은 그대로이고 이력 변경 후는 1,000자로 잘린다
    expect(created.body).toBe(body)
    expect(Array.from((await gateway.history.list(code, {}))[0]?.after ?? '')).toHaveLength(1000)
  })

  // Action Comment 이력의 대상은 수행일과 유형 이름을 담는다.
  // 테스트 코드: CM-082
  it('names the action in the history target of an action comment', async () => {
    // given: Action
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const act = await gateway.actions.create(code, action())

    // when: Action Comment를 쓴다
    await gateway.comments.create(code, { body: '글', actionId: act.id })

    // then: 이력 대상이 "Action Comment (<수행일> <유형>)"이다
    expect((await gateway.history.list(code, {}))[0]).toMatchObject({ category: 'comment', target: `Action Comment (${act.actedOn} 미팅)` })
  })
})

describe('comments 조회와 삭제', () => {
  // 조회는 모든 역할이 하고 없는 Deal은 404이며 다른 Deal 것은 섞이지 않는다.
  // 테스트 코드: CM-082
  it('lets every role read, answers 404 for a missing deal and never mixes deals', async () => {
    // given: 두 Deal에 하나씩 쓴 Comment
    const sales = await mockAs('kim')
    await sales.gateway.comments.create(dealCode(2), { body: 'A' })
    await sales.gateway.comments.create(dealCode(1), { body: 'B' })

    // when·then: user도 그 Deal 것만 읽고 없는 Deal은 404다
    await sales.signInAs(USER_ID.han)
    expect((await sales.gateway.comments.list(dealCode(2))).map((c) => c.body)).toEqual(['A'])
    await expectApiError(sales.gateway.comments.list('20000101-ZZZZ'), 404, 'Deal을 찾을 수 없습니다.')
    await expectApiError(sales.gateway.comments.counts('20000101-ZZZZ'), 404, 'Deal을 찾을 수 없습니다.')
  })

  // 퇴사한 작성자의 Comment는 남고 작성자는 resigned로 보인다. 작성자는 삭제 대신 퇴사 처리된다.
  // 테스트 코드: CM-082
  it('resigns a comment author instead of deleting and keeps the comment', async () => {
    // given: 연결이 Comment뿐인 sales
    const mock = await mockAs('jung')
    const code = dealCode(2)
    await mock.gateway.comments.create(code, { body: '정영업 글' })

    // when: admin이 그 사용자를 삭제한다
    await mock.signInAs(USER_ID.root)
    const result = await mock.gateway.users.remove(USER_ID.jung)

    // then: 퇴사 처리되고 Comment의 작성자는 resigned다
    expect(result).toMatchObject({ outcome: 'resigned' })
    expect((await mock.gateway.comments.list(code))[0]?.author).toMatchObject({ id: USER_ID.jung, status: 'resigned' })
  })

  // 삭제 판정: user 403(없는 id여도) → 없는 Comment 404 → 작성자 아님 403.
  // 테스트 코드: CM-082
  it('judges a delete as read-only 403, then 404, then the author rule', async () => {
    // given: 김영업의 Comment
    const mock = await mockAs('kim')
    const mine = await mock.gateway.comments.create(dealCode(2), { body: '내 글' })
    // when·then: user는 없는 id여도 403, 다른 sales는 403 고정 문구, 없는 id는 404
    await mock.signInAs(USER_ID.han)
    await expectApiError(mock.gateway.comments.remove(NO_SUCH_ID), 403, '이 작업을 할 권한이 없습니다(읽기 전용 계정)')
    await mock.signInAs(USER_ID.park)
    await expectApiError(mock.gateway.comments.remove(mine.id), 403, '본인 Comment 또는 admin만 삭제할 수 있습니다.')
    await expectApiError(mock.gateway.comments.remove(NO_SUCH_ID), 404, 'Comment를 찾을 수 없습니다.')
    // then: Comment가 그대로다
    expect(await mock.gateway.comments.list(dealCode(2))).toHaveLength(1)
  })
})

describe('comments 읽음 처리와 집계', () => {
  // 판정 순서: user 403 → 형식 422 → 없는 Deal 404 → Owner 아님 403. 다른 Deal의 id는 건너뛴다.
  // 테스트 코드: CM-082
  it('judges a mark-read as read-only 403, shape 422, missing deal 404, then owner 403, skipping foreign ids', async () => {
    // given: Owner(김영업)의 Deal 2와 다른 Deal의 읽지 않은 Comment
    const code = dealCode(2)
    const ownerId = await ownerOf(code)
    expect(ownerId).toBe(USER_ID.kim)
    const mock = await mockAs('root')
    const here = await mock.gateway.comments.create(code, { body: '여기' })
    const there = await mock.gateway.comments.create(dealCode(1), { body: '저기' })
    // when·then: user는 403, 형식 위반은 422(없는 Deal보다 먼저), 없는 Deal은 404, Owner 아닌 admin은 403
    await mock.signInAs(USER_ID.han)
    await expectApiError(mock.gateway.comments.markRead(code, [here.id]), 403, '이 작업을 할 권한이 없습니다(읽기 전용 계정)')
    await mock.signInAs(USER_ID.kim)
    await expectApiError(mock.gateway.comments.markRead('20000101-ZZZZ', []), 422)
    await expectApiError(mock.gateway.comments.markRead('20000101-ZZZZ', [here.id]), 404, 'Deal을 찾을 수 없습니다.')
    await mock.signInAs(USER_ID.root)
    await expectApiError(mock.gateway.comments.markRead(code, [here.id]), 403, 'Deal Owner만 Comment를 읽음 처리할 수 있습니다.')
    // when: Owner가 두 id를 읽음 처리한다
    await mock.signInAs(USER_ID.kim)
    await mock.gateway.comments.markRead(code, [here.id, there.id])
    // then: 이 Deal 것만 읽음이 되고 다른 Deal 것은 읽지 않음 그대로이며 이력은 늘지 않는다
    expect((await mock.gateway.comments.list(code))[0]?.readAt).not.toBeNull()
    expect((await mock.gateway.comments.list(dealCode(1)))[0]?.readAt).toBeNull()
    expect((await mock.gateway.history.list(code, {}))[0]).toMatchObject({ after: '등록: 여기' })
  })

  // 501개는 형식 위반 422다.
  // 테스트 코드: CM-082
  it('refuses more than 500 ids with 422', async () => {
    // given: Owner
    const { gateway } = await mockAs('kim')
    // when·then: 500개는 통과하고 501개는 422다
    await gateway.comments.markRead(dealCode(2), Array.from({ length: 500 }, (_, i) => i + 1))
    await expectApiError(gateway.comments.markRead(dealCode(2), Array.from({ length: 501 }, (_, i) => i + 1)), 422)
  })

  // 읽지 않은 수는 Deal 전체와 Action별(1 이상만)이고 Owner가 바뀌어도 읽음 상태는 그대로다.
  // 테스트 코드: CM-082
  it('counts unread by deal and by action and keeps the read state when the owner changes', async () => {
    // given: Owner Deal에 Action 둘, admin이 쓴 읽지 않은 Comment 3건(Deal 1·Action1 2)
    const code = dealCode(2)
    const mock = await mockAs('kim')
    const a1 = await mock.gateway.actions.create(code, action())
    await mock.gateway.actions.create(code, action({ progress: '둘째' }))
    await mock.signInAs(USER_ID.root)
    await mock.gateway.comments.create(code, { body: 'D' })
    const c1 = await mock.gateway.comments.create(code, { body: 'A1', actionId: a1.id })
    await mock.gateway.comments.create(code, { body: 'A1b', actionId: a1.id })
    // when·then: 집계는 전체 3, Action1만 2다
    expect(await mock.gateway.comments.counts(code)).toEqual({ unread: 3, byAction: { [a1.id]: 2 } })
    // when: Owner가 하나를 읽고 Deal의 Owner가 박영업으로 바뀐다
    await mock.signInAs(USER_ID.kim)
    await mock.gateway.comments.markRead(code, [c1.id])
    await mock.signInAs(USER_ID.root)
    const deal = await mock.gateway.deals.get(code)
    await mock.gateway.deals.update(code, { ownerId: USER_ID.park })
    // then: 읽은 것은 계속 읽음이고 새 Owner만 나머지를 읽음 처리한다
    expect(deal.ownerId).toBe(USER_ID.kim)
    expect((await mock.gateway.comments.counts(code)).unread).toBe(2)
    await mock.signInAs(USER_ID.kim)
    await expectApiError(mock.gateway.comments.markRead(code, [1]), 403, 'Deal Owner만 Comment를 읽음 처리할 수 있습니다.')
    await mock.signInAs(USER_ID.park)
    await mock.gateway.comments.markRead(code, (await mock.gateway.comments.list(code)).map((c) => c.id))
    expect(await mock.gateway.comments.counts(code)).toEqual({ unread: 0, byAction: {} })
  })
})

describe('comments와 Action 연동', () => {
  // 등록 Comment는 Owner가 등록하면 읽음, 다른 사람이면 읽지 않음이다.
  // 테스트 코드: CM-082
  it('creates a registration comment as read for the owner and unread for another sales', async () => {
    // given: Owner(김영업)와 다른 sales(박영업)
    const code = dealCode(2)
    const mock = await mockAs('kim')
    // when: 각자 Comment와 함께 Action을 등록한다
    const own = await mock.gateway.actions.create(code, action({ comment: 'Owner 등록' }))
    await mock.signInAs(USER_ID.park)
    const other = await mock.gateway.actions.create(code, action({ comment: '박영업 등록' }))
    // then: Owner 것은 읽음, 박영업 것은 읽지 않음이다
    const byAction = (id: number) => mock.gateway.comments.list(code, { actionId: id }).then((l) => l[0])
    expect((await byAction(own.id))?.readAt).not.toBeNull()
    expect((await byAction(other.id))?.readAt).toBeNull()
  })

  // 등록이 거절되면 Comment도 남지 않는다.
  // 테스트 코드: CM-082
  it('leaves no comment when the registration is refused', async () => {
    // given: Owner
    const code = dealCode(2)
    const { gateway } = await mockAs('kim')
    // when·then: 내용이 비어 등록이 거절된다
    await expectApiError(gateway.actions.create(code, action({ progress: '', nextAction: '', dueDate: '', comment: '남을까' })), 422, '진행사항 또는 Next Action을 입력하세요.')
    // then: Comment가 없다
    expect(await gateway.comments.list(code)).toEqual([])
  })

  // Action 검색어는 Action Comment 본문에도 일치하고 Deal Comment는 찾지 않는다.
  // 테스트 코드: CM-082
  it('finds an action by its comment text and ignores deal comments in the keyword search', async () => {
    // given: Comment가 있는 Action 둘과 Deal Comment
    const code = dealCode(2)
    const { gateway } = await mockAs('kim')
    const a = await gateway.actions.create(code, action({ progress: '가', comment: 'NEEDLE 포함' }))
    await gateway.actions.create(code, action({ progress: '나' }))
    await gateway.comments.create(code, { body: 'needle deal' })
    // when: 대소문자 다르게 검색한다
    const found = await gateway.actions.list(code, { keyword: 'needle' })
    // then: Action Comment가 있는 Action만 나온다
    expect(found.map((x) => x.id)).toEqual([a.id])
  })

  // 수정은 Comment를 바꾸지 않고, Deal을 지우면 Deal 소속 Comment가 모두 지워진다.
  // 테스트 코드: CM-082
  it('keeps comments on action update and deletes every comment of a deleted deal', async () => {
    // given: Action Comment와 Deal Comment
    const code = dealCode(2)
    const { gateway } = await mockAs('kim')
    const a = await gateway.actions.create(code, action({ comment: '글' }))
    await gateway.comments.create(code, { body: 'Deal 글' })
    // when: Action을 수정한다
    await gateway.actions.update(a.id, { type: { name: '미팅' }, progress: '바뀜', nextAction: '견적 재전달', dueDate: '2026-12-01' })
    // then: Comment는 그대로이고 연결 Action 요약은 바뀐 값이다
    const listed = await gateway.comments.list(code)
    expect(listed).toHaveLength(2)
    expect(listed.find((c) => c.actionId === a.id)?.action).toMatchObject({ progress: '바뀜' })
    // when: Deal을 지운다
    await gateway.deals.remove(code, code)
    // then: 삭제 영향은 사전에 2건이었고 Deal이 없다
    await expectApiError(gateway.comments.list(code), 404)
  })
})
