import { afterEach, describe, expect, it, vi } from 'vitest'
import { createLabelsHttp } from './labels'
import { json, noContent, problem, stubFetch, userRefBody } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const label = (over: Record<string, unknown> = {}) => ({
  id: 1,
  category: 'budget',
  name: '단독 예산 확보',
  is_default: true,
  created_by: null,
  created_at: '2026-01-01T09:00:00+09:00',
  updated_at: '2026-01-01T09:00:00+09:00',
  usage_count: 0,
  ...over,
})

describe('labels over HTTP', () => {
  // 목록은 GET /bant-labels로 읽고 기본·직접 만든 Label을 화면 값으로 바꾼다.
  // 테스트 코드: CL-091, CL-092
  it('list reads GET /bant-labels and maps default and custom labels', async () => {
    // given: 서버가 기본 Label과 직접 만든 Label을 돌려준다
    const { calls } = stubFetch(json([label(), label({ id: 2, name: '내 라벨', is_default: false, created_by: userRefBody(1, '김영업'), usage_count: 2 })]))

    // when: 목록을 읽는다
    const labels = await createLabelsHttp().list()

    // then: GET 요청이고 만든 사람·사용 수·시각이 화면 값으로 바뀐다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/bant-labels' })
    expect(labels[0]).toEqual({
      id: 1,
      category: 'budget',
      name: '단독 예산 확보',
      isDefault: true,
      createdBy: null,
      createdAt: '2026-01-01T09:00:00+09:00',
      usageCount: 0,
    })
    expect(labels[1]).toMatchObject({ isDefault: false, usageCount: 2, createdBy: { id: 1, name: '김영업' } })
  })

  // 등록은 구분과 이름을 POST로 보낸다.
  // 테스트 코드: CL-091
  it('create posts the category and the name', async () => {
    // given: 서버가 201을 돌려준다
    const { calls } = stubFetch(json(label({ id: 3, name: '신규', is_default: false }), 201))

    // when: need에 '신규'를 등록한다
    const created = await createLabelsHttp().create('need', '신규')

    // then: 본문이 {category, name}이고 결과가 반환된다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/bant-labels', body: { category: 'need', name: '신규' } })
    expect(created).toMatchObject({ id: 3, name: '신규' })
  })

  // 등록 실패(409·422·403)는 서버 문구를 그대로 담은 화면 kind로 던진다.
  // 테스트 코드: CL-091
  it.each([
    [409, 'already-exists', '같은 구분에 이미 있는 Label 이름입니다.', 'conflict'],
    [422, 'invalid-value', 'Label 이름을 입력하세요.', 'validation'],
    [422, 'invalid-value', 'Label 이름은 50자 이내로 입력하세요.', 'validation'],
    [403, 'forbidden', '이 작업을 수행할 권한이 없습니다.', 'forbidden'],
  ])('create failure %i "%s" keeps the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 해당 오류를 돌려준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: Label을 등록한다 → 상태·kind가 맞고 서버 문구가 그대로다
    await expect(createLabelsHttp().create('budget', 'x')).rejects.toMatchObject({ status, kind, message: detail })
  })

  // 이름 변경은 PATCH로 새 이름만 보낸다.
  // 테스트 코드: CL-091
  it('rename patches the name', async () => {
    // given: 서버가 200을 돌려준다
    const { calls } = stubFetch(json(label({ name: '새 이름' })))

    // when: id 1의 이름을 바꾼다
    await createLabelsHttp().rename(1, '새 이름')

    // then: PATCH /bant-labels/1에 {name}을 보냈다
    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/bant-labels/1', body: { name: '새 이름' } })
  })

  // 삭제는 DELETE를 보내고 204를 성공으로 본다.
  // 테스트 코드: CL-091
  it('remove deletes and accepts 204', async () => {
    // given: 서버가 204를 돌려준다
    const { calls } = stubFetch(noContent())

    // when: id 1을 삭제한다
    await expect(createLabelsHttp().remove(1)).resolves.toBeUndefined()

    // then: 아무 값 없이 성공하고 DELETE를 보냈다
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/bant-labels/1' })
  })

  // 사용 중이라는 409 거절은 서버 문구를 담은 conflict로 던진다.
  // 테스트 코드: CL-091
  it('remove maps the in-use refusal to a conflict', async () => {
    // given: 서버가 사용 중 409를 돌려준다
    stubFetch(problem(409, 'invalid-state', '사용 중인 Label은 삭제할 수 없습니다. (Deal 3건)'))

    // when·then: id 1을 삭제한다 → kind가 conflict이고 서버 문구 그대로다
    await expect(createLabelsHttp().remove(1)).rejects.toMatchObject({ kind: 'conflict', message: '사용 중인 Label은 삭제할 수 없습니다. (Deal 3건)' })
  })
})
