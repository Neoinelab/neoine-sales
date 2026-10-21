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
  memo: '',
}

describe('actions.list over HTTP (AC-14~16)', () => {
  it('sends GET /deals/{code}/actions without a query when nothing is set', async () => {
    const { calls } = stubFetch(json({ items: [] }))

    await createActionsHttp().list(CODE, {})

    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/actions` })
  })

  it('reads the items array of the {items} answer and maps each action', async () => {
    stubFetch(json({ items: [serverAction({ id: 2, action: '두 번째' }), serverAction({ id: 1, action: '첫 번째' })] }))

    const list = await createActionsHttp().list(CODE, {})

    expect(list.map((a) => [a.id, a.progress, a.type])).toEqual([
      [2, '두 번째', '미팅'],
      [1, '첫 번째', '미팅'],
    ])
  })

  it('never sends offset or limit (the server has no paging)', async () => {
    const { calls } = stubFetch(json({ items: [] }))

    await createActionsHttp().list(CODE, { keyword: 'ROI' })

    const sent = query(calls[0]?.path ?? '')
    expect(sent.has('offset')).toBe(false)
    expect(sent.has('limit')).toBe(false)
  })

  it('maps every filter to its query key with YYYY-MM-DD dates and integer id values', async () => {
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
      sort: 'dueAsc',
    }

    await createActionsHttp().list(CODE, full)

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

  it.each([
    ['actedDesc', 'acted_at_desc'],
    ['actedAsc', 'acted_at_asc'],
    ['dueAsc', 'due_date_asc'],
  ] as const)('maps sort %s to %s', async (sort, wire) => {
    const { calls } = stubFetch(json({ items: [] }))

    await createActionsHttp().list(CODE, { sort })

    expect(query(calls[0]?.path ?? '').get('sort')).toBe(wire)
  })

  it('leaves out empty values instead of sending blanks', async () => {
    const { calls } = stubFetch(json({ items: [] }))

    await createActionsHttp().list(CODE, { keyword: '', actedFrom: '', dueTo: '' })

    expect(calls[0]?.path).toBe(`/api/v1/deals/${CODE}/actions`)
  })

  it('shows the 422 message of a reversed range as the server wrote it', async () => {
    stubFetch(problem(422, 'invalid-value', '수행일 범위의 시작은 끝보다 늦을 수 없습니다.'))

    await expect(createActionsHttp().list(CODE, { actedFrom: '2026-10-20', actedTo: '2026-10-01' })).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '수행일 범위의 시작은 끝보다 늦을 수 없습니다.',
    })
  })

  it('shows the 404 of an unknown deal', async () => {
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    await expect(createActionsHttp().list(CODE, {})).rejects.toMatchObject({ status: 404, message: 'Deal을 찾을 수 없습니다.' })
  })
})

describe('actions.create over HTTP (AC-01·02·05)', () => {
  it('posts the snake_case content to /deals/{code}/actions and maps the 201 answer', async () => {
    const { calls } = stubFetch(json(serverAction(), 201, { Location: `/api/v1/deal-actions/${ACTION_ID}` }))

    const created = await createActionsHttp().create(CODE, newAction)

    expect(calls[0]).toMatchObject({ method: 'POST', path: `/api/v1/deals/${CODE}/actions` })
    expect(calls[0]?.body).toEqual({
      action_type: { name: '미팅' },
      action: '고객사 방문',
      next_action: '견적 재전달',
      due_date: '2026-10-22',
      memo: '',
    })
    expect(created).toMatchObject({ id: ACTION_ID, progress: '고객사 방문', type: '미팅', typeId: ACTION_TYPE_ID, statusKey: 'prospecting', forecastKey: 'pipeline' })
  })

  it('never sends acted_at or an actor (the server fills them)', async () => {
    const { calls } = stubFetch(json(serverAction(), 201))

    await createActionsHttp().create(CODE, newAction)

    const body = calls[0]?.body as Record<string, unknown>
    expect(body).not.toHaveProperty('acted_at')
    expect(body).not.toHaveProperty('actor_user_id')
  })

  it('sends an empty due date as null', async () => {
    const { calls } = stubFetch(json(serverAction(), 201))

    await createActionsHttp().create(CODE, { ...newAction, dueDate: '' })

    expect((calls[0]?.body as Record<string, unknown>).due_date).toBeNull()
  })

  it('sends a very long text untouched', async () => {
    const { calls } = stubFetch(json(serverAction(), 201))

    await createActionsHttp().create(CODE, { ...newAction, progress: '가'.repeat(5000), memo: '나'.repeat(20000) })

    const body = calls[0]?.body as { action: string; memo: string }
    expect(body.action).toHaveLength(5000)
    expect(body.memo).toHaveLength(20000)
  })

  it('sends status_changes with the resolution of a closing', async () => {
    const { calls } = stubFetch(json(serverAction({ status_key: 'contract_completed', forecast_key: 'won' }), 201))

    const created = await createActionsHttp().create(CODE, {
      ...newAction,
      statusChanges: [{
        change: { field: 'statusKey', value: 'contract_completed' },
        resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-15' },
      }],
    })

    expect(calls[0]?.body).toMatchObject({
      status_changes: [
        {
          change: { field: 'status_key', value: 'contract_completed' },
          resolution: { revenue_amount: 1_800_000_000, revenue_date: '2026-10-15' },
        },
      ],
    })
    expect(created).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
  })

  it.each([
    [403, 'forbidden', '이 작업을 할 권한이 없습니다(읽기 전용 계정)', 'forbidden'],
    [404, 'not-found', 'Deal을 찾을 수 없습니다.', 'not-found'],
    [409, 'invalid-state', '다른 변경과 충돌했습니다.', 'conflict'],
    [422, 'invalid-value', '진행사항을 입력하세요.', 'validation'],
    [422, 'request-validation', '요청 형식이 올바르지 않습니다.', 'validation'],
  ])('shows the %s answer %s with the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createActionsHttp().create(CODE, newAction)).rejects.toMatchObject({ status, kind, message: detail })
  })
})

describe('actions.list never sends the old action_type enum query (AC-16)', () => {
  it('has no action_type key when only a type id is set', async () => {
    const { calls } = stubFetch(json({ items: [] }))

    await createActionsHttp().list(CODE, { typeId: ACTION_TYPE_ID })

    expect(query(calls[0]?.path ?? '').has('action_type')).toBe(false)
  })
})

describe('actions.create type choice (AC-7·10)', () => {
  it('sends the id object for a listed type and maps the {id, name} answer', async () => {
    const { calls } = stubFetch(json(serverAction(), 201))

    await createActionsHttp().create(CODE, { ...newAction, type: { id: ACTION_TYPE_ID } })

    expect((calls[0]?.body as { action_type: unknown }).action_type).toEqual({ id: ACTION_TYPE_ID })
  })

  it('sends exactly one of id and name, never both', async () => {
    const { calls } = stubFetch(json(serverAction(), 201), json(serverAction(), 201))

    await createActionsHttp().create(CODE, { ...newAction, type: { name: '웨비나' } })
    await createActionsHttp().create(CODE, { ...newAction, type: { id: ACTION_TYPE_ID } })

    const sent = calls.map((c) => Object.keys((c.body as { action_type: object }).action_type))
    expect(sent).toEqual([['name'], ['id']])
  })

  it('shows the unknown type message as the server wrote it', async () => {
    stubFetch(problem(422, 'invalid-value', '선택한 유형이 없습니다. 목록에서 다시 선택하세요.'))

    await expect(createActionsHttp().create(CODE, { ...newAction, type: { id: 99 } })).rejects.toMatchObject({
      status: 422,
      kind: 'validation',
      message: '선택한 유형이 없습니다. 목록에서 다시 선택하세요.',
    })
  })
})

describe('actions.update over HTTP (AC-10·11)', () => {
  it('puts the content to /deal-actions/{id} and maps the answer', async () => {
    const { calls } = stubFetch(json(serverAction({ action: '수정한 진행사항', action_type: { id: 5, name: '기타' } })))

    const updated = await createActionsHttp().update(ACTION_ID, { type: { id: 5 }, progress: '수정한 진행사항', nextAction: '수정한 Next', dueDate: '2026-11-01', memo: '메모' })

    expect(calls[0]).toMatchObject({ method: 'PUT', path: `/api/v1/deal-actions/${ACTION_ID}` })
    expect(calls[0]?.body).toEqual({
      action_type: { id: 5 },
      action: '수정한 진행사항',
      next_action: '수정한 Next',
      due_date: '2026-11-01',
      memo: '메모',
    })
    expect(updated).toMatchObject({ id: ACTION_ID, progress: '수정한 진행사항', type: '기타', typeId: 5 })
  })

  it('shows the 403 message for another sales exactly as the server wrote it', async () => {
    stubFetch(problem(403, 'forbidden', '본인 Action 또는 admin만 수정할 수 있습니다.'))

    await expect(createActionsHttp().update(ACTION_ID, newAction)).rejects.toMatchObject({
      status: 403,
      kind: 'forbidden',
      message: '본인 Action 또는 admin만 수정할 수 있습니다.',
    })
  })

  it.each([
    [404, 'not-found', 'Action을 찾을 수 없습니다.', 'not-found'],
    [422, 'invalid-value', 'Next Action을 입력하세요.', 'validation'],
  ])('shows the %s answer with the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createActionsHttp().update(ACTION_ID, newAction)).rejects.toMatchObject({ status, kind, message: detail })
  })
})

describe('actions.remove over HTTP (AC-12)', () => {
  it('deletes /deal-actions/{id} and resolves with nothing on 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createActionsHttp().remove(ACTION_ID)).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `/api/v1/deal-actions/${ACTION_ID}` })
    expect(calls[0]?.body).toBeUndefined()
  })

  it('shows the 403 message for another sales exactly as the server wrote it', async () => {
    stubFetch(problem(403, 'forbidden', '본인 Action 또는 admin만 삭제할 수 있습니다.'))

    await expect(createActionsHttp().remove(ACTION_ID)).rejects.toMatchObject({
      status: 403,
      kind: 'forbidden',
      message: '본인 Action 또는 admin만 삭제할 수 있습니다.',
    })
  })

  it('shows the 404 of an unknown action', async () => {
    stubFetch(problem(404, 'not-found', 'Action을 찾을 수 없습니다.'))

    await expect(createActionsHttp().remove(ACTION_ID)).rejects.toMatchObject({ status: 404, message: 'Action을 찾을 수 없습니다.' })
  })
})

describe('http gateway wiring (AC-22)', () => {
  it('uses the real actions adapter instead of the 501 placeholder', async () => {
    const { calls } = stubFetch(json({ items: [] }))

    await expect(createHttpGateway().actions.list(CODE, {})).resolves.toEqual([])

    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/actions` })
  })
})

describe('actions.list status filter (AC-18)', () => {
  it.each([
    ['open', 'open'],
    ['done', 'done'],
    ['notDone', 'not_done'],
    ['closed', 'closed'],
  ] as const)('maps %s to next_action_status=%s', async (status, wire) => {
    const { calls } = stubFetch(json({ items: [] }))

    await createActionsHttp().list(CODE, { nextActionStatus: status })

    expect(query(calls[0]?.path ?? '').get('next_action_status')).toBe(wire)
  })
})

describe('actions.create with a partial input (AC-1·2)', () => {
  it('posts a progress-only content with an empty Next Action and a null due date, and maps null fields', async () => {
    const { calls } = stubFetch(
      json(serverAction({ next_action: null, due_date: null, next_action_status: null }), 201),
    )

    const created = await createActionsHttp().create(CODE, { ...newAction, nextAction: '', dueDate: '' })

    expect(calls[0]?.body).toMatchObject({ action: '고객사 방문', next_action: '', due_date: null })
    expect(created).toMatchObject({ nextAction: null, dueDate: null, nextActionStatus: null })
  })

  it('posts a Next-Action-only content with an empty progress', async () => {
    const { calls } = stubFetch(json(serverAction({ action: null }), 201))

    const created = await createActionsHttp().create(CODE, { ...newAction, progress: '' })

    expect(calls[0]?.body).toMatchObject({ action: '', next_action: '견적 재전달' })
    expect(created.progress).toBeNull()
  })

  it('shows the 422 of an empty content with the server message', async () => {
    stubFetch(problem(422, 'invalid-value', '진행사항 또는 Next Action을 입력하세요.'))

    await expect(createActionsHttp().create(CODE, { ...newAction, progress: '', nextAction: '', dueDate: '' })).rejects.toMatchObject({
      status: 422,
      message: '진행사항 또는 Next Action을 입력하세요.',
    })
  })
})

describe('actions.changeNextActionStatus over HTTP (AC-8~12)', () => {
  it('puts the snake_case status and the memo to /deal-actions/{id}/next-action-status and maps the answer', async () => {
    const { calls } = stubFetch(
      json(serverAction({ next_action_status: 'not_done', next_action_closed_at: '2026-10-16T10:00:00+09:00', memo: '기존\n접음' })),
    )

    const changed = await createActionsHttp().changeNextActionStatus(ACTION_ID, { status: 'notDone', memo: '접음' })

    expect(calls[0]).toMatchObject({ method: 'PUT', path: `/api/v1/deal-actions/${ACTION_ID}/next-action-status` })
    expect(calls[0]?.body).toEqual({ status: 'not_done', memo: '접음' })
    expect(changed).toMatchObject({ id: ACTION_ID, nextActionStatus: 'notDone', nextActionClosedAt: '2026-10-16T10:00:00+09:00', memo: '기존\n접음' })
  })

  it.each([
    ['open', 'open'],
    ['done', 'done'],
  ] as const)('sends %s as %s with an empty memo', async (status, wire) => {
    const { calls } = stubFetch(json(serverAction()))

    await createActionsHttp().changeNextActionStatus(ACTION_ID, { status, memo: '' })

    expect(calls[0]?.body).toEqual({ status: wire, memo: '' })
  })

  it.each([
    [403, 'forbidden', '본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.', 'forbidden'],
    [404, 'not-found', 'Action을 찾을 수 없습니다.', 'not-found'],
    [409, 'invalid-state', '이미 Open 상태입니다.', 'conflict'],
    [409, 'invalid-state', 'Next Action이 없는 Action은 상태를 바꿀 수 없습니다.', 'conflict'],
    [422, 'invalid-value', '메모를 남길 수 없습니다.', 'validation'],
  ])('shows the %s answer with the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createActionsHttp().changeNextActionStatus(ACTION_ID, { status: 'done', memo: '' })).rejects.toMatchObject({
      status,
      kind,
      message: detail,
    })
  })
})
