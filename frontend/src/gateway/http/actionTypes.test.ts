import { afterEach, describe, expect, it, vi } from 'vitest'
import { ACTION_TYPE_ID } from '../../test/fixtures/serverAction'
import { serverUserRef } from '../../test/fixtures/serverDeal'
import { createActionTypesHttp } from './actionTypes'
import { createHttpGateway } from './index'
import { json, noContent, problem, stubFetch } from './testHelpers'
import { USER_ID } from '../../test/fake/seed/ids'

afterEach(() => vi.unstubAllGlobals())

const type = (over: Record<string, unknown> = {}) => ({
  id: ACTION_TYPE_ID,
  name: '미팅',
  is_default: true,
  created_by: null,
  usage_count: 0,
  created_at: '2026-01-01T09:00:00+09:00',
  updated_at: '2026-01-01T09:00:00+09:00',
  ...over,
})

describe('action types over HTTP (AC-1~6)', () => {
  it('list reads GET /action-types and maps default and custom types in the server order', async () => {
    const { calls } = stubFetch(json([type(), type({ id: 2, name: '웨비나', is_default: false, created_by: serverUserRef({ id: USER_ID.kim }), usage_count: 2 })]))

    const list = await createActionTypesHttp().list()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/action-types' })
    expect(list.map((t) => [t.name, t.isDefault, t.usageCount])).toEqual([
      ['미팅', true, 0],
      ['웨비나', false, 2],
    ])
    expect(list[1]?.createdBy).toMatchObject({ id: USER_ID.kim })
  })

  it('create posts only the name', async () => {
    const { calls } = stubFetch(json(type({ id: 3, name: '신규', is_default: false }), 201, { Location: '/api/v1/action-types/3' }))

    const created = await createActionTypesHttp().create('신규')

    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/action-types', body: { name: '신규' } })
    expect(created).toMatchObject({ id: 3, name: '신규' })
  })

  it.each([
    [409, 'already-exists', '이미 있는 유형 이름입니다.', 'conflict'],
    [422, 'invalid-value', '유형을 입력하세요.', 'validation'],
    [422, 'invalid-value', '유형은 50자 이내로 입력하세요.', 'validation'],
    [403, 'forbidden', '이 작업을 수행할 권한이 없습니다.', 'forbidden'],
  ])('create failure %i "%s" keeps the server message', async (status, serverKind, detail, kind) => {
    stubFetch(problem(status, serverKind, detail))

    await expect(createActionTypesHttp().create('x')).rejects.toMatchObject({ status, kind, message: detail })
  })

  it('rename patches the name of that type', async () => {
    const { calls } = stubFetch(json(type({ name: '대면 미팅' })))

    const renamed = await createActionTypesHttp().rename(ACTION_TYPE_ID, '대면 미팅')

    expect(calls[0]).toMatchObject({ method: 'PATCH', path: `/api/v1/action-types/${ACTION_TYPE_ID}`, body: { name: '대면 미팅' } })
    expect(renamed.name).toBe('대면 미팅')
  })

  it('remove deletes and accepts 204', async () => {
    const { calls } = stubFetch(noContent())

    await expect(createActionTypesHttp().remove(ACTION_TYPE_ID)).resolves.toBeUndefined()

    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `/api/v1/action-types/${ACTION_TYPE_ID}` })
  })

  it('remove maps the in-use refusal to a conflict with the count', async () => {
    stubFetch(problem(409, 'invalid-state', '사용 중인 유형은 삭제할 수 없습니다. (Action 3건)'))

    await expect(createActionTypesHttp().remove(ACTION_TYPE_ID)).rejects.toMatchObject({
      status: 409,
      kind: 'conflict',
      message: '사용 중인 유형은 삭제할 수 없습니다. (Action 3건)',
    })
  })
})

describe('http gateway wiring', () => {
  it('uses the real action types adapter instead of a placeholder', async () => {
    const { calls } = stubFetch(json([]))

    await createHttpGateway().actionTypes.list()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/action-types' })
  })
})
