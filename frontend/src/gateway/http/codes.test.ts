import { afterEach, describe, expect, it, vi } from 'vitest'
import { createCodesHttp } from './codes'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const code = (over: Record<string, unknown> = {}) => ({
  id: 1,
  kind: 'status',
  key: 'prospecting',
  name: '기회발굴',
  order: 1,
  locked: true,
  outcome: 'open',
  probability_hint: null,
  ...over,
})

describe('codes over HTTP', () => {
  // 코드 목록을 읽어 화면 값으로 바꾼다.
  // 테스트 코드: CD-068
  it('all reads GET /codes and maps both lists', async () => {
    // given: 서버가 Status 1개와 Forecast 1개를 돌려준다
    const { calls } = stubFetch(
      json({ statuses: [code()], forecasts: [code({ id: 2, kind: 'forecast', key: 'best', name: 'Best', locked: false, probability_hint: '51–75' })] }),
    )

    // when: all()을 부른다
    const set = await createCodesHttp().all()

    // then: GET /api/v1/codes를 보내고 probability_hint를 probabilityHint로 바꾼다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/codes' })
    expect(set.statuses[0]).toEqual({ id: 1, kind: 'status', key: 'prospecting', name: '기회발굴', order: 1, locked: true, outcome: 'open', probabilityHint: null })
    expect(set.forecasts[0]).toMatchObject({ key: 'best', probabilityHint: '51–75' })
  })

  // 사용 현황을 읽어 usage_count를 usageCount로 바꾼다.
  // 테스트 코드: CD-068
  it('list reads GET /codes/usage for the kind and keeps the usage count', async () => {
    // given: 서버가 사용 수 3을 돌려준다
    const { calls } = stubFetch(json([code({ usage_count: 3 })]))

    // when: list('status')를 부른다
    const rows = await createCodesHttp().list('status')

    // then: kind 쿼리로 요청하고 usageCount를 돌려준다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/codes/usage?kind=status' })
    expect(rows[0]).toMatchObject({ key: 'prospecting', usageCount: 3 })
  })

  // 서버 403은 상태 403 forbidden 오류다.
  // 테스트 코드: CD-068
  it('list shows the server 403 for a non-admin', async () => {
    // given: 서버가 403을 돌려준다
    stubFetch(problem(403, 'forbidden', '이 작업을 수행할 권한이 없습니다.'))

    // when: list('status')를 부른다
    const result = createCodesHttp().list('status')

    // then: 상태 403 forbidden 오류다
    await expect(result).rejects.toMatchObject({ status: 403, kind: 'forbidden' })
  })

  // 추가는 kind, name, 힌트를 보내고 새 코드를 돌려준다.
  // 테스트 코드: CD-069
  it('create posts kind, name and the hint, and returns the new code', async () => {
    // given: 서버가 201로 새 코드를 돌려준다
    const { calls } = stubFetch(json(code({ id: 9, kind: 'forecast', key: 'upside', name: 'Upside', locked: false, usage_count: 0 }), 201))

    // when: 힌트와 함께 추가한다
    const created = await createCodesHttp().create({ kind: 'forecast', name: 'Upside', probabilityHint: '10–20' })

    // then: POST /codes 본문에 probability_hint가 있고 새 코드를 돌려준다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/codes', body: { kind: 'forecast', name: 'Upside', probability_hint: '10–20' } })
    expect(created).toMatchObject({ id: 9, key: 'upside', usageCount: 0 })
  })

  // 힌트가 없으면 null을 보낸다.
  // 테스트 코드: CD-069
  it('create sends a null hint when none is given', async () => {
    // given: 서버가 201로 돌려준다
    const { calls } = stubFetch(json(code({ usage_count: 0 }), 201))

    // when: 힌트 없이 추가한다
    await createCodesHttp().create({ kind: 'status', name: '보류' })

    // then: probability_hint는 null이다
    expect(calls[0]?.body).toEqual({ kind: 'status', name: '보류', probability_hint: null })
  })

  // 중복 이름 409는 conflict이고 서버 문구 그대로다.
  // 테스트 코드: CD-069
  it('create maps a duplicate name to a conflict with the server message', async () => {
    // given: 서버가 409를 돌려준다
    stubFetch(problem(409, 'already-exists', '같은 이름의 코드가 이미 있습니다.'))

    // when: 중복 이름으로 추가한다
    const result = createCodesHttp().create({ kind: 'status', name: '기회발굴' })

    // then: conflict 오류이고 문구는 서버 detail 그대로다
    await expect(result).rejects.toMatchObject({
      status: 409,
      kind: 'conflict',
      message: '같은 이름의 코드가 이미 있습니다.',
    })
  })

  // 빈 이름 422는 validation이고 서버 문구 그대로다.
  // 테스트 코드: CD-069
  it('create maps a blank name to a validation error with the server message', async () => {
    // given: 서버가 422를 돌려준다
    stubFetch(problem(422, 'invalid-value', '이름을 입력하세요.'))

    // when: 빈 이름으로 추가한다
    const result = createCodesHttp().create({ kind: 'status', name: '' })

    // then: validation 오류이고 문구는 서버 detail 그대로다
    await expect(result).rejects.toMatchObject({ kind: 'validation', message: '이름을 입력하세요.' })
  })

  // 이름 변경은 PATCH /codes/{id}에 name을 보낸다.
  // 테스트 코드: CD-069
  it('rename patches the name', async () => {
    // given: 서버가 바뀐 코드를 돌려준다
    const { calls } = stubFetch(json(code({ name: '신규 발굴', usage_count: 0 })))

    // when: 이름을 바꾼다
    const renamed = await createCodesHttp().rename(1, '신규 발굴')

    // then: PATCH 본문이 {name}이고 새 이름을 돌려준다
    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/codes/1', body: { name: '신규 발굴' } })
    expect(renamed.name).toBe('신규 발굴')
  })

  // 순서 변경은 종류 전체 id 목록을 PUT으로 보낸다.
  // 테스트 코드: CD-069
  it('reorder puts the whole id list of the kind', async () => {
    // given: 서버가 새 순서를 돌려준다
    const { calls } = stubFetch(json([code({ id: 2, order: 1, usage_count: 0 }), code({ id: 1, order: 2, usage_count: 0 })]))

    // when: 순서를 바꾼다
    const rows = await createCodesHttp().reorder('status', [2, 1])

    // then: PUT /codes/order 본문이 {kind, ordered_ids}이고 새 순서를 돌려준다
    expect(calls[0]).toMatchObject({ method: 'PUT', path: '/api/v1/codes/order', body: { kind: 'status', ordered_ids: [2, 1] } })
    expect(rows.map((r) => r.id)).toEqual([2, 1])
  })

  // 순서 목록 오류 422는 validation이고 서버 문구 그대로다.
  // 테스트 코드: CD-069
  it('reorder shows the server message for a wrong id list', async () => {
    // given: 서버가 422를 돌려준다
    stubFetch(problem(422, 'invalid-value', '순서 목록이 올바르지 않습니다.'))

    // when: 잘못된 id 목록으로 순서를 바꾼다
    const result = createCodesHttp().reorder('status', [1])

    // then: validation 오류이고 문구는 서버 detail 그대로다
    await expect(result).rejects.toMatchObject({ kind: 'validation', message: '순서 목록이 올바르지 않습니다.' })
  })

  // 삭제는 DELETE를 보내고 204를 성공으로 받는다.
  // 테스트 코드: CD-069
  it('remove deletes and accepts 204', async () => {
    // given: 서버가 204를 돌려준다
    const { calls } = stubFetch(noContent())

    // when: 삭제한다
    const result = createCodesHttp().remove(1)

    // then: 성공(undefined)이고 DELETE /codes/1을 보낸다
    await expect(result).resolves.toBeUndefined()
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/codes/1' })
  })

  // 잠금·사용 중 409는 conflict이고 서버 문구 그대로다.
  // 테스트 코드: CD-069
  it.each([
    '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.',
    '사용 중인 코드는 삭제할 수 없습니다. (Deal 2건)',
  ])('remove maps "%s" to a conflict', async (detail) => {
    // given: 서버가 409를 돌려준다
    stubFetch(problem(409, 'invalid-state', detail))

    // when: 삭제한다
    const result = createCodesHttp().remove(1)

    // then: conflict 오류이고 문구는 서버 detail 그대로다
    await expect(result).rejects.toMatchObject({ status: 409, kind: 'conflict', message: detail })
  })

  // 모르는 결과(outcome)는 해석 불가 오류로 거절한다.
  // 테스트 코드: CD-070
  it('rejects an outcome the screens do not know', async () => {
    // given: 서버가 Forecast outcome "weird"를 돌려준다
    stubFetch(json({ statuses: [], forecasts: [code({ kind: 'forecast', outcome: 'weird' })] }))

    // when: 코드 목록을 읽는다
    const result = createCodesHttp().all()

    // then: "서버 응답을 해석할 수 없습니다." 오류다
    await expect(result).rejects.toMatchObject({ message: '서버 응답을 해석할 수 없습니다.' })
  })
})
