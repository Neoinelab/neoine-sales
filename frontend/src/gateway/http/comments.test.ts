import { afterEach, describe, expect, it, vi } from 'vitest'
import { COMMENT_ID, serverComment } from '../../test/fixtures/serverComment'
import { CODE } from '../../test/fixtures/serverDeal'
import { createCommentsHttp } from './comments'
import { createHttpGateway } from './index'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

describe('comments.list over HTTP', () => {
  // 조건이 없으면 쿼리 없이 GET하고 {items}를 화면 Comment로 바꾼다(서버 순서 그대로).
  // 테스트 코드: CM-081
  it('sends GET /deals/{code}/comments without a query and maps the items in server order', async () => {
    // given: 서버가 Comment 둘을 준다
    const { calls } = stubFetch(json({ items: [serverComment({ id: 2, body: '둘' }), serverComment({ id: 1, body: '하나' })] }))

    // when: 조건 없이 목록을 부른다
    const list = await createCommentsHttp().list(CODE)

    // then: 쿼리 없는 GET이고 서버 순서 그대로 화면 이름으로 바뀐다
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/comments` })
    expect(list.map((c) => [c.id, c.body, c.dealCode])).toEqual([[2, '둘', CODE], [1, '하나', CODE]])
  })

  // actionId가 있을 때만 action_id 쿼리를 보낸다.
  // 테스트 코드: CM-081
  it('sends action_id only when an actionId is given', async () => {
    // given: 서버가 빈 목록을 준다
    const { calls } = stubFetch(json({ items: [] }), json({ items: [] }))

    // when: 빈 조건과 actionId 조건으로 부른다
    await createCommentsHttp().list(CODE, {})
    await createCommentsHttp().list(CODE, { actionId: 41 })

    // then: 앞은 쿼리가 없고 뒤는 action_id=41이다
    expect(calls[0]?.path).toBe(`/api/v1/deals/${CODE}/comments`)
    expect(calls[1]?.path).toBe(`/api/v1/deals/${CODE}/comments?action_id=41`)
  })

  // 읽기 실패는 서버 상태·문구 그대로의 오류가 된다.
  // 테스트 코드: CM-081
  it('shows the server status and message of a failed read', async () => {
    // given: 서버가 404를 준다
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    // when·then: 목록을 부르면 서버 문구 그대로 거절된다
    await expect(createCommentsHttp().list(CODE)).rejects.toMatchObject({ status: 404, kind: 'not-found', message: 'Deal을 찾을 수 없습니다.' })
  })
})

describe('comments.create over HTTP', () => {
  // actionId가 없으면 body만 보내고 action_id 키는 생략한다(Deal Comment).
  // 테스트 코드: CM-081
  it('posts only the body, without action_id, for a deal comment and maps the 201 answer', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverComment(), 201))

    // when: actionId 없이 만든다
    const created = await createCommentsHttp().create(CODE, { body: '예산 회의 예정' })

    // then: POST 본문이 {body}뿐이고 응답이 화면 Comment로 바뀐다
    expect(calls[0]).toMatchObject({ method: 'POST', path: `/api/v1/deals/${CODE}/comments`, body: { body: '예산 회의 예정' } })
    expect(calls[0]?.body).not.toHaveProperty('action_id')
    expect(created).toMatchObject({ id: COMMENT_ID, actionId: null, action: null, readAt: null })
  })

  // actionId가 있으면 action_id를 함께 보낸다(Action Comment).
  // 테스트 코드: CM-081
  it('posts action_id with the body for an action comment', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverComment({ action_id: 41 }), 201))

    // when: actionId 41로 만든다
    await createCommentsHttp().create(CODE, { body: '견적서 초안 공유함', actionId: 41 })

    // then: 본문이 {body, action_id}다
    expect(calls[0]?.body).toEqual({ body: '견적서 초안 공유함', action_id: 41 })
  })

  // 본문은 가공하지 않고 보낸다(정규화는 서버).
  // 테스트 코드: CM-081
  it('sends the body untouched, including line breaks and surrounding spaces', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverComment(), 201))

    // when: 줄바꿈과 앞뒤 공백이 있는 본문으로 만든다
    await createCommentsHttp().create(CODE, { body: '  1줄\n2줄  ' })

    // then: 그대로 간다
    expect((calls[0]?.body as { body: string }).body).toBe('  1줄\n2줄  ')
  })

  // 서버 거절(403·404·422)은 상태·문구 그대로 넘긴다.
  // 테스트 코드: CM-081
  it.each([
    [403, 'forbidden', '이 작업을 할 권한이 없습니다(읽기 전용 계정)', 'forbidden'],
    [404, 'not-found', 'Deal을 찾을 수 없습니다.', 'not-found'],
    [422, 'invalid-value', 'Comment에는 NUL 문자를 쓸 수 없습니다', 'validation'],
    [422, 'invalid-value', '선택한 Action이 이 Deal에 없습니다.', 'validation'],
  ])('shows the %s answer with the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 거절한다
    stubFetch(problem(status, serverKind, detail))

    // when·then: 서버 상태·종류·문구 그대로 거절된다
    await expect(createCommentsHttp().create(CODE, { body: 'x' })).rejects.toMatchObject({ status, kind, message: detail })
  })
})

describe('comments.remove over HTTP', () => {
  // 삭제는 DELETE /deal-comments/{id}이고 204는 값 없이 끝난다.
  // 테스트 코드: CM-081
  it('sends DELETE /deal-comments/{id} and resolves with nothing for 204', async () => {
    // given: 서버가 204를 준다
    const { calls } = stubFetch(noContent())

    // when·then: 삭제하면 값 없이 끝나고 경로가 맞다
    await expect(createCommentsHttp().remove(COMMENT_ID)).resolves.toBeUndefined()
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `/api/v1/deal-comments/${COMMENT_ID}` })
  })

  // 403·404는 서버 문구 그대로다.
  // 테스트 코드: CM-081
  it.each([
    [403, 'forbidden', '본인 Comment 또는 admin만 삭제할 수 있습니다.'],
    [404, 'not-found', 'Comment를 찾을 수 없습니다.'],
  ])('shows the %s answer with the server message', async (status, serverKind, detail) => {
    // given: 서버가 거절한다
    stubFetch(problem(status, serverKind, detail))

    // when·then: 서버 문구 그대로 거절된다
    await expect(createCommentsHttp().remove(COMMENT_ID)).rejects.toMatchObject({ status, message: detail })
  })
})

describe('comments.markRead over HTTP', () => {
  // 읽음 처리는 POST …/comment-reads에 comment_ids를 보내고 204는 값 없이 끝난다.
  // 테스트 코드: CM-081
  it('posts comment_ids to /deals/{code}/comment-reads and resolves with nothing for 204', async () => {
    // given: 서버가 204를 준다
    const { calls } = stubFetch(noContent())

    // when·then: 읽음 처리하면 값 없이 끝나고 본문이 {comment_ids}다
    await expect(createCommentsHttp().markRead(CODE, [3, 5, 8])).resolves.toBeUndefined()
    expect(calls[0]).toMatchObject({ method: 'POST', path: `/api/v1/deals/${CODE}/comment-reads`, body: { comment_ids: [3, 5, 8] } })
  })

  // Owner가 아니면 403 서버 문구 그대로다.
  // 테스트 코드: CM-081
  it('shows the owner-only refusal with the server message', async () => {
    // given: 서버가 403을 준다
    stubFetch(problem(403, 'forbidden', 'Deal Owner만 Comment를 읽음 처리할 수 있습니다.'))

    // when·then: 서버 문구 그대로 거절된다
    await expect(createCommentsHttp().markRead(CODE, [1])).rejects.toMatchObject({
      status: 403,
      message: 'Deal Owner만 Comment를 읽음 처리할 수 있습니다.',
    })
  })
})

describe('comments.counts over HTTP', () => {
  // 집계는 GET …/comment-counts이고 {unread, byAction}으로 바뀐다.
  // 테스트 코드: CM-081
  it('reads GET /deals/{code}/comment-counts and maps it to {unread, byAction}', async () => {
    // given: 서버가 집계를 준다
    const { calls } = stubFetch(json({ unread: 3, by_action: [{ action_id: 41, unread: 2 }] }))

    // when: 집계를 읽는다
    const counts = await createCommentsHttp().counts(CODE)

    // then: 경로가 맞고 byAction이 action id 키 객체다
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/comment-counts` })
    expect(counts).toEqual({ unread: 3, byAction: { 41: 2 } })
  })
})

describe('http gateway wiring', () => {
  // 조립된 HTTP 게이트웨이에 comments가 있고 수정(update) 메서드는 없다.
  // 테스트 코드: CM-081, CM-066
  it('exposes comments with the five methods and no update', () => {
    // when: HTTP 게이트웨이를 만든다
    const gateway = createHttpGateway()

    // then: 다섯 메서드뿐이다
    expect(Object.keys(gateway.comments).sort()).toEqual(['counts', 'create', 'list', 'markRead', 'remove'])
  })
})
