import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ActionQuery } from '../../shared/model/types'
import { ACTION_ID, ACTION_TYPE_ID, serverAction } from '../../test/fixtures/serverAction'
import { CODE } from '../../test/fixtures/serverDeal'
import { createActionsHttp } from './actions'
import { createHttpGateway } from './index'
import { json, noContent, problem, stubFetch } from './testHelpers'
import { USER_ID } from '../../test/fake/seed/ids'

afterEach(() => vi.unstubAllGlobals())

const query = (path: string) => new URL(path, 'http://localhost').searchParams

const newAction = {
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-10-22',
  comment: '',
}

describe('actions.list over HTTP', () => {
  // 조건이 없으면 쿼리 없이 GET /deals/{code}/actions를 보낸다.
  // 테스트 코드: NA-066
  it('sends GET /deals/{code}/actions without a query when nothing is set', async () => {
    // given: 서버가 빈 목록을 준다.
    const { calls } = stubFetch(json({ items: [] }))

    // when: 빈 조건으로 목록을 부른다.
    await createActionsHttp().list(CODE, {})

    // then: 경로에 쿼리가 없는 GET 요청이다.
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/actions` })
  })

  // {items} 응답의 items 배열을 읽어 각 Action을 화면 모양으로 바꾼다.
  // 테스트 코드: NA-066
  it('reads the items array of the {items} answer and maps each action', async () => {
    // given: 서버가 Action 두 건이 든 {items}를 준다.
    stubFetch(json({ items: [serverAction({ id: 2, action: '두 번째' }), serverAction({ id: 1, action: '첫 번째' })] }))

    // when: 목록을 부른다.
    const list = await createActionsHttp().list(CODE, {})

    // then: 서버 순서 그대로 화면 Action으로 바뀐다.
    expect(list.map((a) => [a.id, a.progress, a.type])).toEqual([
      [2, '두 번째', '미팅'],
      [1, '첫 번째', '미팅'],
    ])
  })

  // offset·limit는 보내지 않는다(서버에 페이지가 없다).
  // 테스트 코드: NA-066
  it('never sends offset or limit (the server has no paging)', async () => {
    // given: 서버가 빈 목록을 준다.
    const { calls } = stubFetch(json({ items: [] }))

    // when: 키워드 조건으로 목록을 부른다.
    await createActionsHttp().list(CODE, { keyword: 'ROI' })

    // then: 쿼리에 offset·limit가 없다.
    const sent = query(calls[0]?.path ?? '')
    expect(sent.has('offset')).toBe(false)
    expect(sent.has('limit')).toBe(false)
  })

  // 채운 조건 전부를 서버 쿼리 이름(날짜는 YYYY-MM-DD, id는 정수 문자열)으로 보낸다.
  // 테스트 코드: NA-066
  it('maps every filter to its query key with YYYY-MM-DD dates and integer id values', async () => {
    // given: 서버가 빈 목록을 준다.
    const { calls } = stubFetch(json({ items: [] }))
    const full: ActionQuery = {
      typeId: ACTION_TYPE_ID,
      actorId: USER_ID.kim,
      keyword: 'ROI',
      actedFrom: '2026-10-01',
      actedTo: '2026-10-15',
      dueFrom: '2026-10-16',
      dueTo: '2026-10-31',
      nextActionStatus: 'closed',
      sort: 'dueDate',
      order: 'asc',
    }

    // when: 화면 조건을 전부 채워 목록을 부른다.
    await createActionsHttp().list(CODE, full)

    // then: 쿼리가 action_type_id·actor_user_id·keyword·날짜 넷·next_action_status·sort 서버 이름이다.
    const sent = query(calls[0]?.path ?? '')
    expect(Object.fromEntries(sent)).toEqual({
      action_type_id: String(ACTION_TYPE_ID),
      actor_user_id: String(USER_ID.kim),
      keyword: 'ROI',
      acted_from: '2026-10-01',
      acted_to: '2026-10-15',
      due_from: '2026-10-16',
      due_to: '2026-10-31',
      next_action_status: 'closed',
      sort: 'due_date_asc',
    })
  })

  // 정렬 열·방향을 서버 sort 값으로 바꾼다.
  // 테스트 코드: NA-066
  it.each([
    ['actedAt', 'desc', 'acted_at_desc'],
    ['actedAt', 'asc', 'acted_at_asc'],
    ['dueDate', 'asc', 'due_date_asc'],
    ['dueDate', 'desc', 'due_date_desc'],
    ['actor', 'asc', 'actor_asc'],
    ['actor', 'desc', 'actor_desc'],
    ['type', 'asc', 'action_type_asc'],
    ['type', 'desc', 'action_type_desc'],
    ['nextActionStatus', 'asc', 'next_action_status_asc'],
    ['nextActionStatus', 'desc', 'next_action_status_desc'],
  ] as const)('maps sort %s %s to %s', async (sort, order, wire) => {
    // given: 서버가 빈 목록을 준다.
    const { calls } = stubFetch(json({ items: [] }))

    // when: 열·방향을 주고 목록을 부른다.
    await createActionsHttp().list(CODE, { sort, order })

    // then: sort 값이 서버 이름이다.
    expect(query(calls[0]?.path ?? '').get('sort')).toBe(wire)
  })

  // 열과 방향이 모두 있을 때만 sort를 보낸다.
  // 테스트 코드: NA-066
  it.each([
    [{ sort: 'actor' }],
    [{ order: 'desc' }],
    [{}],
  ] as const)('sends no sort parameter unless both sort and order are given: %j', async (partial) => {
    // given: 서버가 빈 목록을 준다.
    const { calls } = stubFetch(json({ items: [] }))

    // when: 열 또는 방향 하나만 주고 목록을 부른다.
    await createActionsHttp().list(CODE, partial)

    // then: sort 쿼리가 없다.
    expect(query(calls[0]?.path ?? '').has('sort')).toBe(false)
  })

  // 빈 값은 보내지 않고 쿼리에서 뺀다.
  // 테스트 코드: NA-066
  it('leaves out empty values instead of sending blanks', async () => {
    // given: 서버가 빈 목록을 준다.
    const { calls } = stubFetch(json({ items: [] }))

    // when: 빈 문자열 조건으로 목록을 부른다.
    await createActionsHttp().list(CODE, { keyword: '', actedFrom: '', dueTo: '' })

    // then: 쿼리가 없는 경로다.
    expect(calls[0]?.path).toBe(`/api/v1/deals/${CODE}/actions`)
  })

  // 범위 역전 422는 서버 상태와 문구 그대로의 오류가 된다.
  // 테스트 코드: NA-067
  it('shows the 422 message of a reversed range as the server wrote it', async () => {
    // given: 서버가 422 "수행일 범위의 시작은 끝보다 늦을 수 없습니다."를 준다.
    stubFetch(problem(422, 'invalid-value', '수행일 범위의 시작은 끝보다 늦을 수 없습니다.'))

    // when·then: 거꾸로 된 수행일 범위로 목록을 부르면 서버 상태·문구 그대로 거절된다.
    await expect(createActionsHttp().list(CODE, { actedFrom: '2026-10-20', actedTo: '2026-10-01' })).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '수행일 범위의 시작은 끝보다 늦을 수 없습니다.',
    })
  })

  // 없는 Deal 404는 서버 상태와 문구 그대로의 오류가 된다.
  // 테스트 코드: NA-067
  it('shows the 404 of an unknown deal', async () => {
    // given: 서버가 404 "Deal을 찾을 수 없습니다."를 준다.
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    // when·then: 목록을 부르면 서버 상태·문구 그대로 거절된다.
    await expect(createActionsHttp().list(CODE, {})).rejects.toMatchObject({ status: 404, message: 'Deal을 찾을 수 없습니다.' })
  })
})

describe('actions.create over HTTP', () => {
  // 등록은 snake_case 내용을 POST로 보내고 201 응답을 화면 Action으로 바꾼다.
  // 테스트 코드: AC-089
  it('posts the snake_case content to /deals/{code}/actions and maps the 201 answer', async () => {
    // given: 서버가 201과 Location, Action을 준다
    const { calls } = stubFetch(json(serverAction(), 201, { Location: `/api/v1/deal-actions/${ACTION_ID}` }))

    // when: 내용을 등록한다
    const created = await createActionsHttp().create(CODE, newAction)

    // then: POST /deals/{code}/actions에 서버 이름의 본문이 간다
    expect(calls[0]).toMatchObject({ method: 'POST', path: `/api/v1/deals/${CODE}/actions` })
    expect(calls[0]?.body).toEqual({
      action_type: { name: '미팅' },
      action: '고객사 방문',
      next_action: '견적 재전달',
      due_date: '2026-10-22',
      comment: '',
    })
    // then: 응답이 화면 Action으로 바뀐다
    expect(created).toMatchObject({ id: ACTION_ID, progress: '고객사 방문', type: '미팅', typeId: ACTION_TYPE_ID, statusKey: 'prospecting', forecastKey: 'pipeline' })
  })

  // 수행일시와 담당자는 보내지 않는다.
  // 테스트 코드: AC-089
  it('never sends acted_on or an actor (the server fills them)', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverAction(), 201))

    // when: 내용을 등록한다
    await createActionsHttp().create(CODE, newAction)

    // then: 본문에 acted_on·actor_user_id가 없다
    const body = calls[0]?.body as Record<string, unknown>
    expect(body).not.toHaveProperty('acted_on')
    expect(body).not.toHaveProperty('actor_user_id')
  })

  // 빈 Due Date는 null로 보낸다.
  // 테스트 코드: AC-089
  it('sends an empty due date as null', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverAction(), 201))

    // when: Due가 빈 내용을 등록한다
    await createActionsHttp().create(CODE, { ...newAction, dueDate: '' })

    // then: due_date가 null이다
    expect((calls[0]?.body as Record<string, unknown>).due_date).toBeNull()
  })

  // 아주 긴 텍스트도 가공하지 않고 보낸다.
  // 테스트 코드: AC-089
  it('sends a very long text untouched', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverAction(), 201))

    // when: 5,000자 진행사항과 20,000자 Comment로 등록한다
    await createActionsHttp().create(CODE, { ...newAction, progress: '가'.repeat(5000), comment: '나'.repeat(20000) })

    // then: 길이가 그대로 간다
    const body = calls[0]?.body as { action: string; comment: string }
    expect(body.action).toHaveLength(5000)
    expect(body.comment).toHaveLength(20000)
    expect(body).not.toHaveProperty('memo')
  })

  // 이전 Next Action id는 같은 POST 본문에 실어 한 번에 보낸다.
  // 테스트 코드: AC-089
  it('sends close_previous_next_action_id in the same POST body (one request)', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverAction(), 201))

    // when: 닫을 id를 지정해 등록한다
    await createActionsHttp().create(CODE, { ...newAction, closePreviousNextActionId: 41 })

    // then: 요청은 하나이고 본문에 close_previous_next_action_id가 있다
    expect(calls).toHaveLength(1)
    expect(calls[0]).toMatchObject({ method: 'POST', body: { close_previous_next_action_id: 41 } })
  })

  // 닫을 id를 주지 않으면 필드를 보내지 않는다.
  // 테스트 코드: AC-089
  it('does not send the field when it is not asked for', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverAction(), 201))

    // when: 닫을 id 없이 등록한다
    await createActionsHttp().create(CODE, newAction)

    // then: 본문에 그 필드가 없다
    expect(calls[0]?.body).not.toHaveProperty('close_previous_next_action_id')
  })

  // 이전 Next Action이 바뀌면 서버 문구를 그대로 보인다.
  // 테스트 코드: AC-089
  it('shows the server message when the previous next action has changed', async () => {
    // given: 서버가 409를 준다
    stubFetch(problem(409, 'invalid-state', '이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요.'))

    // when·then: 닫을 id로 등록하면 서버 문구의 409로 거절된다
    await expect(createActionsHttp().create(CODE, { ...newAction, closePreviousNextActionId: 41 })).rejects.toMatchObject({
      status: 409,
      message: '이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요.',
    })
  })

  // 동반 변경은 각자 resolution과 함께 status_changes로 보낸다.
  // 테스트 코드: AC-089
  it('sends status_changes with the resolution of a closing', async () => {
    // given: 서버가 계약완료·Won 스냅숏의 201을 준다
    const { calls } = stubFetch(json(serverAction({ status_key: 'contract_completed', forecast_key: 'won' }), 201))

    // when: 매출 답이 있는 계약완료 변경으로 등록한다
    const created = await createActionsHttp().create(CODE, {
      ...newAction,
      statusChanges: [{
        change: { field: 'statusKey', value: 'contract_completed' },
        resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' },
      }],
    })

    // then: 본문의 status_changes가 서버 이름이다
    expect(calls[0]?.body).toMatchObject({
      status_changes: [
        {
          change: { field: 'status_key', value: 'contract_completed' },
          resolution: { revenue_amount: 1_800_000_000, revenue_date: '2026-10-15' },
        },
      ],
    })
    // then: 응답 스냅숏이 계약완료·Won이다
    expect(created).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
  })

  // 거절 응답(403·404·409·422)은 서버 상태·종류·문구 그대로 보인다.
  // 테스트 코드: AC-089
  it.each([
    [403, 'forbidden', '이 작업을 할 권한이 없습니다(읽기 전용 계정)', 'forbidden'],
    [404, 'not-found', 'Deal을 찾을 수 없습니다.', 'not-found'],
    [409, 'invalid-state', '다른 변경과 충돌했습니다.', 'conflict'],
    [422, 'invalid-value', '진행사항을 입력하세요.', 'validation'],
    [422, 'request-validation', '요청 형식이 올바르지 않습니다.', 'validation'],
  ])('shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 거절 응답을 준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: 등록하면 서버 상태·종류·문구 그대로 거절된다
    await expect(createActionsHttp().create(CODE, newAction)).rejects.toMatchObject({ status, kind, message: detail })
  })
})

describe('actions.list never sends the old action_type enum query', () => {
  // 유형 id만 줘도 구 enum `action_type` 쿼리는 보내지 않는다.
  // 테스트 코드: NA-066
  it('has no action_type key when only a type id is set', async () => {
    // given: 서버가 빈 목록을 준다.
    const { calls } = stubFetch(json({ items: [] }))

    // when: 유형 id 조건으로 목록을 부른다.
    await createActionsHttp().list(CODE, { typeId: ACTION_TYPE_ID })

    // then: action_type 쿼리는 없다.
    expect(query(calls[0]?.path ?? '').has('action_type')).toBe(false)
  })
})

describe('actions.create type choice', () => {
  // 목록에서 고른 유형은 id 객체로 보낸다.
  // 테스트 코드: AC-089
  it('sends the id object for a listed type and maps the {id, name} answer', async () => {
    // given: 서버가 201을 준다
    const { calls } = stubFetch(json(serverAction(), 201))

    // when: 유형 id로 등록한다
    await createActionsHttp().create(CODE, { ...newAction, type: { id: ACTION_TYPE_ID } })

    // then: action_type은 {id}다
    expect((calls[0]?.body as { action_type: unknown }).action_type).toEqual({ id: ACTION_TYPE_ID })
  })

  // 유형은 id와 이름 중 하나만 보낸다.
  // 테스트 코드: AC-089
  it('sends exactly one of id and name, never both', async () => {
    // given: 서버가 201을 두 번 준다
    const { calls } = stubFetch(json(serverAction(), 201), json(serverAction(), 201))

    // when: 이름으로, id로 각각 등록한다
    await createActionsHttp().create(CODE, { ...newAction, type: { name: '웨비나' } })
    await createActionsHttp().create(CODE, { ...newAction, type: { id: ACTION_TYPE_ID } })

    // then: 보낸 키는 [name], [id]다
    const sent = calls.map((c) => Object.keys((c.body as { action_type: object }).action_type))
    expect(sent).toEqual([['name'], ['id']])
  })

  // 없는 유형 문구를 서버가 쓴 그대로 보인다.
  // 테스트 코드: AC-089
  it('shows the unknown type message as the server wrote it', async () => {
    // given: 서버가 422를 준다
    stubFetch(problem(422, 'invalid-value', '선택한 유형이 없습니다. 목록에서 다시 선택하세요.'))

    // when·then: 없는 유형 id로 등록하면 서버 문구의 422로 거절된다
    await expect(createActionsHttp().create(CODE, { ...newAction, type: { id: 99 } })).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '선택한 유형이 없습니다. 목록에서 다시 선택하세요.',
    })
  })
})

describe('actions.update over HTTP', () => {
  // 수정은 PUT으로 내용 칸만 보내고 응답을 화면 Action으로 바꾼다.
  // 테스트 코드: AC-089
  it('puts the content to /deal-actions/{id} and maps the answer', async () => {
    // given: 서버가 수정된 Action을 준다
    const { calls } = stubFetch(json(serverAction({ action: '수정한 진행사항', action_type: { id: 5, name: '기타' } })))

    // when: 내용을 수정한다
    const updated = await createActionsHttp().update(ACTION_ID, { type: { id: 5 }, progress: '수정한 진행사항', nextAction: '수정한 Next', dueDate: '2026-11-01' })

    // then: PUT /deal-actions/{id}에 내용 칸 본문이 간다
    expect(calls[0]).toMatchObject({ method: 'PUT', path: `/api/v1/deal-actions/${ACTION_ID}` })
    expect(calls[0]?.body).toEqual({
      action_type: { id: 5 },
      action: '수정한 진행사항',
      next_action: '수정한 Next',
      due_date: '2026-11-01',
    })
    expect(calls[0]?.body).not.toHaveProperty('memo')
    expect(calls[0]?.body).not.toHaveProperty('comment')
    // then: 응답이 화면 Action으로 바뀐다
    expect(updated).toMatchObject({ id: ACTION_ID, progress: '수정한 진행사항', type: '기타', typeId: 5 })
  })

  // 다른 sales의 수정 403 문구를 서버가 쓴 그대로 보인다.
  // 테스트 코드: AC-089
  it('shows the 403 message for another sales exactly as the server wrote it', async () => {
    // given: 서버가 403을 준다
    stubFetch(problem(403, 'forbidden', '본인 Action 또는 admin만 수정할 수 있습니다.'))

    // when·then: 수정하면 서버 문구의 403으로 거절된다
    await expect(createActionsHttp().update(ACTION_ID, newAction)).rejects.toMatchObject({
      status: 403,
      kind: 'forbidden',
      message: '본인 Action 또는 admin만 수정할 수 있습니다.',
    })
  })

  // 수정 실패(404·422)는 서버 문구 그대로 보인다.
  // 테스트 코드: AC-089
  it.each([
    [404, 'not-found', 'Action을 찾을 수 없습니다.', 'not-found'],
    [422, 'invalid-value', 'Next Action을 입력하세요.', 'validation'],
  ])('shows the %s answer with the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 거절 응답을 준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: 수정하면 서버 상태·종류·문구 그대로 거절된다
    await expect(createActionsHttp().update(ACTION_ID, newAction)).rejects.toMatchObject({ status, kind, message: detail })
  })
})

describe('actions.remove over HTTP', () => {
  // 삭제는 DELETE를 보내고 204면 값 없이 끝난다.
  // 테스트 코드: AC-089
  it('deletes /deal-actions/{id} and resolves with nothing on 204', async () => {
    // given: 서버가 204를 준다
    const { calls } = stubFetch(noContent())

    // when·then: 삭제하면 값 없이 끝난다
    await expect(createActionsHttp().remove(ACTION_ID)).resolves.toBeUndefined()

    // then: 요청은 DELETE /deal-actions/{id}이고 본문이 없다
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `/api/v1/deal-actions/${ACTION_ID}` })
    expect(calls[0]?.body).toBeUndefined()
  })

  // 다른 sales의 삭제 403 문구를 서버가 쓴 그대로 보인다.
  // 테스트 코드: AC-089
  it('shows the 403 message for another sales exactly as the server wrote it', async () => {
    // given: 서버가 403을 준다
    stubFetch(problem(403, 'forbidden', '본인 Action 또는 admin만 삭제할 수 있습니다.'))

    // when·then: 삭제하면 서버 문구의 403으로 거절된다
    await expect(createActionsHttp().remove(ACTION_ID)).rejects.toMatchObject({
      status: 403,
      kind: 'forbidden',
      message: '본인 Action 또는 admin만 삭제할 수 있습니다.',
    })
  })

  // 없는 Action 삭제 404 문구를 보인다.
  // 테스트 코드: AC-089
  it('shows the 404 of an unknown action', async () => {
    // given: 서버가 404를 준다
    stubFetch(problem(404, 'not-found', 'Action을 찾을 수 없습니다.'))

    // when·then: 삭제하면 서버 문구의 404로 거절된다
    await expect(createActionsHttp().remove(ACTION_ID)).rejects.toMatchObject({ status: 404, message: 'Action을 찾을 수 없습니다.' })
  })
})

describe('http gateway wiring', () => {
  // HTTP 게이트웨이의 actions는 실제 어댑터를 쓴다.
  // 테스트 코드: AC-089
  it('uses the real actions adapter instead of the 501 placeholder', async () => {
    // given: 서버가 빈 목록을 준다
    const { calls } = stubFetch(json({ items: [] }))

    // when·then: 게이트웨이로 목록을 부르면 빈 목록이다
    await expect(createHttpGateway().actions.list(CODE, {})).resolves.toEqual([])

    // then: GET /deals/{code}/actions가 나간다
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/actions` })
  })
})

describe('actions.list status filter', () => {
  // 상태 필터를 서버 이름(notDone -> not_done)으로 보낸다.
  // 테스트 코드: NA-066
  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['notDone', 'not_done'],
    ['closed', 'closed'],
  ] as const)('maps %s to next_action_status=%s', async (status, wire) => {
    // given: 서버가 빈 목록을 준다.
    const { calls } = stubFetch(json({ items: [] }))

    // when: 상태 필터를 주고 목록을 부른다.
    await createActionsHttp().list(CODE, { nextActionStatus: status })

    // then: 쿼리 값이 서버 이름이다.
    expect(query(calls[0]?.path ?? '').get('next_action_status')).toBe(wire)
  })
})

describe('actions.create with a partial input', () => {
  // 진행사항만 내용은 빈 Next Action과 null Due로 보내고 null 응답 필드를 그대로 둔다.
  // 테스트 코드: AC-089
  it('posts a progress-only content with an empty Next Action and a null due date, and maps null fields', async () => {
    // given: 서버가 Next Action 칸이 null인 201을 준다
    const { calls } = stubFetch(
      json(serverAction({ next_action: null, due_date: null, next_action_status: null }), 201),
    )

    // when: 진행사항만 있는 내용을 등록한다
    const created = await createActionsHttp().create(CODE, { ...newAction, nextAction: '', dueDate: '' })

    // then: 본문이 빈 Next Action과 null Due다
    expect(calls[0]?.body).toMatchObject({ action: '고객사 방문', next_action: '', due_date: null })
    // then: 응답의 null 필드가 null이다
    expect(created).toMatchObject({ nextAction: null, dueDate: null, nextActionStatus: null })
  })

  // Next Action만 내용은 빈 진행사항으로 보내고 null 진행사항을 그대로 둔다.
  // 테스트 코드: AC-089
  it('posts a Next-Action-only content with an empty progress', async () => {
    // given: 서버가 진행사항이 null인 201을 준다
    const { calls } = stubFetch(json(serverAction({ action: null }), 201))

    // when: Next Action만 있는 내용을 등록한다
    const created = await createActionsHttp().create(CODE, { ...newAction, progress: '' })

    // then: 본문의 action이 빈 문자열이다
    expect(calls[0]?.body).toMatchObject({ action: '', next_action: '견적 재전달' })
    // then: 응답 진행사항이 null이다
    expect(created.progress).toBeNull()
  })

  // 빈 내용 422는 서버 문구를 그대로 보인다.
  // 테스트 코드: AC-089
  it('shows the 422 of an empty content with the server message', async () => {
    // given: 서버가 422를 준다
    stubFetch(problem(422, 'invalid-value', '진행사항 또는 Next Action을 입력하세요.'))

    // when·then: 빈 내용으로 등록하면 서버 문구의 422로 거절된다
    await expect(createActionsHttp().create(CODE, { ...newAction, progress: '', nextAction: '', dueDate: '' })).rejects.toMatchObject({
      status: 422,
      message: '진행사항 또는 Next Action을 입력하세요.',
    })
  })
})

describe('actions.changeNextActionStatus over HTTP', () => {
  // 상태 변경은 PUT …/next-action-status에 {status, comment}를 보내고 응답을 화면 Action으로 바꾼다.
  // 테스트 코드: NA-066
  it('puts the snake_case status and the comment to /deal-actions/{id}/next-action-status and maps the answer', async () => {
    // given: 서버가 종료(미수행) Action을 돌려준다.
    const { calls } = stubFetch(
      json(serverAction({ next_action_status: 'not_done', next_action_closed_on: '2026-10-16' })),
    )

    // when: 상태 notDone, Comment "접음"으로 바꾼다.
    const changed = await createActionsHttp().changeNextActionStatus(ACTION_ID, { status: 'notDone', comment: '접음' })

    // then: PUT 본문이 {status: not_done, comment: 접음}이고 응답이 화면 Action으로 바뀐다.
    expect(calls[0]).toMatchObject({ method: 'PUT', path: `/api/v1/deal-actions/${ACTION_ID}/next-action-status` })
    expect(calls[0]?.body).toEqual({ status: 'not_done', comment: '접음' })
    expect(changed).toMatchObject({ id: ACTION_ID, nextActionStatus: 'notDone', nextActionClosedOn: '2026-10-16' })
  })

  // open·done 상태도 서버 이름과 빈 Comment로 보낸다.
  // 테스트 코드: NA-066
  it.each([
    ['open', 'open'],
    ['done', 'done'],
  ] as const)('sends %s as %s with an empty comment', async (status, wire) => {
    // given: 서버가 Action을 돌려준다.
    const { calls } = stubFetch(json(serverAction()))

    // when: 빈 Comment로 상태를 바꾼다.
    await createActionsHttp().changeNextActionStatus(ACTION_ID, { status, comment: '' })

    // then: 본문이 서버 상태 이름과 빈 Comment다.
    expect(calls[0]?.body).toEqual({ status: wire, comment: '' })
  })

  // 상태 변경 실패(403·404·409·422)는 서버 상태·문구 그대로의 오류가 된다.
  // 테스트 코드: NA-067
  it.each([
    [403, 'forbidden', '본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.', 'forbidden'],
    [404, 'not-found', 'Action을 찾을 수 없습니다.', 'not-found'],
    [409, 'invalid-state', '이미 Open 상태입니다.', 'conflict'],
    [409, 'invalid-state', 'Next Action이 없는 Action은 상태를 바꿀 수 없습니다.', 'conflict'],
    [422, 'invalid-value', 'Comment에는 NUL 문자를 쓸 수 없습니다', 'validation'],
  ])('shows the %s answer with the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 거절 응답을 준다.
    stubFetch(problem(status, serverKind, detail))

    // when·then: 상태를 바꾸면 서버 상태·종류·문구 그대로 거절된다.
    await expect(createActionsHttp().changeNextActionStatus(ACTION_ID, { status: 'done', comment: '' })).rejects.toMatchObject({
      status,
      kind,
      message: detail,
    })
  })
})

describe('actions.create with a performed day (acted_on)', () => {
  // 수행일이 없으면 본문에 acted_on 키가 없고, 있으면 ISO 날짜 그대로 보낸다.
  // 테스트 코드: AC-109
  it('sends acted_on only when a day is given and keeps it as an ISO date', async () => {
    // given: 서버가 201과 Action을 준다
    const { calls } = stubFetch(json(serverAction(), 201), json(serverAction(), 201))

    // when: 수행일 없이 등록한다
    await createActionsHttp().create(CODE, newAction)
    // then: 첫 본문에는 acted_on 키가 없다
    expect(calls[0]?.body).not.toHaveProperty('acted_on')

    // when: 수행일 2026-11-10으로 등록한다
    await createActionsHttp().create(CODE, { ...newAction, actedOn: '2026-11-10' })
    // then: 두 번째 본문에는 acted_on이 ISO 날짜 문자열로 담긴다
    expect(calls[1]?.body).toMatchObject({ acted_on: '2026-11-10' })
  })

  // 수정도 수행일이 없으면 acted_on 키를 보내지 않고, 있으면 ISO 날짜 그대로 보낸다.
  // 테스트 코드: AC-109
  it('sends acted_on on update only when a day is given and keeps it as an ISO date', async () => {
    // given: 서버가 200과 Action을 준다
    const { calls } = stubFetch(json(serverAction()), json(serverAction()))

    // when: 수행일 없이 수정한다
    await createActionsHttp().update(ACTION_ID, newAction)
    // then: 첫 본문에는 acted_on 키가 없다
    expect(calls[0]?.body).not.toHaveProperty('acted_on')

    // when: 수행일 2026-11-10으로 수정한다
    const withDay = { ...newAction, actedOn: '2026-11-10' }
    await createActionsHttp().update(ACTION_ID, withDay)
    // then: 두 번째 본문에는 acted_on이 ISO 날짜 문자열로 담긴다
    expect(calls[1]?.body).toMatchObject({ acted_on: '2026-11-10' })
  })
})
