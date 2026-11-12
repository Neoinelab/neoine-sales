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

describe('action types over HTTP', () => {
  // 목록은 GET /action-types로 읽고 서버 순서 그대로 화면 값으로 바꾼다.
  // 테스트 코드: CL-091, CL-092
  it('list reads GET /action-types and maps default and custom types in the server order', async () => {
    // given: 서버가 기본·직접 만든 유형을 돌려준다
    const { calls } = stubFetch(json([type(), type({ id: 2, name: '웨비나', is_default: false, created_by: serverUserRef({ id: USER_ID.kim }), usage_count: 2 })]))

    // when: 목록을 읽는다
    const list = await createActionTypesHttp().list()

    // then: GET 요청이고 이름·기본 여부·사용 수·만든 사람이 바뀐다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/action-types' })
    expect(list.map((t) => [t.name, t.isDefault, t.usageCount])).toEqual([
      ['미팅', true, 0],
      ['웨비나', false, 2],
    ])
    expect(list[1]?.createdBy).toMatchObject({ id: USER_ID.kim })
  })

  // 등록은 이름만 POST로 보낸다.
  // 테스트 코드: CL-091
  it('create posts only the name', async () => {
    // given: 서버가 201을 돌려준다
    const { calls } = stubFetch(json(type({ id: 3, name: '신규', is_default: false }), 201, { Location: '/api/v1/action-types/3' }))

    // when: '신규'를 등록한다
    const created = await createActionTypesHttp().create('신규')

    // then: 본문이 {name}뿐이고 결과가 반환된다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/action-types', body: { name: '신규' } })
    expect(created).toMatchObject({ id: 3, name: '신규' })
  })

  // 등록 실패(409·422·403)는 서버 문구를 그대로 담은 화면 kind로 던진다.
  // 테스트 코드: CL-091
  it.each([
    [409, 'already-exists', '이미 있는 유형 이름입니다.', 'conflict'],
    [422, 'invalid-value', '유형을 입력하세요.', 'validation'],
    [422, 'invalid-value', '유형은 50자 이내로 입력하세요.', 'validation'],
    [403, 'forbidden', '이 작업을 수행할 권한이 없습니다.', 'forbidden'],
  ])('create failure %i "%s" keeps the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 해당 오류를 돌려준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: 유형을 등록한다 → 상태·kind가 맞고 서버 문구가 그대로다
    await expect(createActionTypesHttp().create('x')).rejects.toMatchObject({ status, kind, message: detail })
  })

  // 이름 변경은 그 유형 경로로 PATCH한다.
  // 테스트 코드: CL-091
  it('rename patches the name of that type', async () => {
    // given: 서버가 200을 돌려준다
    const { calls } = stubFetch(json(type({ name: '대면 미팅' })))

    // when: 유형 이름을 바꾼다
    const renamed = await createActionTypesHttp().rename(ACTION_TYPE_ID, '대면 미팅')

    // then: PATCH 경로와 본문이 맞고 새 이름이 반환된다
    expect(calls[0]).toMatchObject({ method: 'PATCH', path: `/api/v1/action-types/${ACTION_TYPE_ID}`, body: { name: '대면 미팅' } })
    expect(renamed.name).toBe('대면 미팅')
  })

  // 삭제는 DELETE를 보내고 204를 성공으로 본다.
  // 테스트 코드: CL-091
  it('remove deletes and accepts 204', async () => {
    // given: 서버가 204를 돌려준다
    const { calls } = stubFetch(noContent())

    // when: 유형을 삭제한다
    await expect(createActionTypesHttp().remove(ACTION_TYPE_ID)).resolves.toBeUndefined()

    // then: 아무 값 없이 성공하고 DELETE를 보냈다
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: `/api/v1/action-types/${ACTION_TYPE_ID}` })
  })

  // 사용 중이라는 409 거절은 건수가 든 서버 문구의 conflict로 던진다.
  // 테스트 코드: CL-091
  it('remove maps the in-use refusal to a conflict with the count', async () => {
    // given: 서버가 사용 중 409를 돌려준다
    stubFetch(problem(409, 'invalid-state', '사용 중인 유형은 삭제할 수 없습니다. (Action 3건)'))

    // when·then: 유형을 삭제한다 → 상태 409, kind conflict, 서버 문구 그대로다
    await expect(createActionTypesHttp().remove(ACTION_TYPE_ID)).rejects.toMatchObject({
      status: 409,
      kind: 'conflict',
      message: '사용 중인 유형은 삭제할 수 없습니다. (Action 3건)',
    })
  })
})

describe('http gateway wiring', () => {
  // HTTP 게이트웨이의 유형 어댑터는 자리표시자가 아니라 실제 어댑터다.
  it('uses the real action types adapter instead of a placeholder', async () => {
    // given: 서버가 빈 목록을 돌려준다
    const { calls } = stubFetch(json([]))

    // when: HTTP 게이트웨이로 유형 목록을 읽는다
    await createHttpGateway().actionTypes.list()

    // then: GET /action-types를 보냈다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/action-types' })
  })
})
