import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpGateway } from './index'
import { createVendorsHttp } from './vendors'
import { json, noContent, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const vendor = (over: Record<string, unknown> = {}) => ({
  id: 1,
  name: 'Silverfort',
  usage_count: 3,
  created_at: '2026-10-01T09:00:00+09:00',
  updated_at: '2026-10-01T09:00:00+09:00',
  ...over,
})

describe('vendors over HTTP', () => {
  // 목록은 GET /vendors로 읽고 Solution 없는 화면 값으로 바꾼다.
  // 테스트 코드: CL-091, CL-092
  it('list reads GET /vendors and maps the vendors without solutions', async () => {
    // given: 서버가 Vendor 하나를 돌려준다
    const { calls } = stubFetch(json([vendor()]))

    // when: 목록을 읽는다
    const vendors = await createVendorsHttp().list()

    // then: GET 요청이고 {id, name, usageCount}로 바뀐다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/vendors' })
    expect(vendors).toEqual([{ id: 1, name: 'Silverfort', usageCount: 3 }])
  })

  // 등록은 이름을 POST로 보낸다.
  // 테스트 코드: CL-091
  it('create posts the name', async () => {
    // given: 서버가 201을 돌려준다
    const { calls } = stubFetch(json(vendor({ usage_count: 0 }), 201, { Location: '/api/v1/vendors/1' }))

    // when: 'Silverfort'를 등록한다
    const created = await createVendorsHttp().create('Silverfort')

    // then: 본문이 {name}이고 사용 0인 Vendor가 반환된다
    expect(calls[0]).toMatchObject({ method: 'POST', path: '/api/v1/vendors', body: { name: 'Silverfort' } })
    expect(created).toEqual({ id: 1, name: 'Silverfort', usageCount: 0 })
  })

  // 이름 변경은 그 Vendor 경로로 PATCH한다.
  // 테스트 코드: CL-091
  it('rename patches the name of the vendor', async () => {
    // given: 서버가 200을 돌려준다
    const { calls } = stubFetch(json(vendor({ name: 'New' })))

    // when: id 1의 이름을 바꾼다
    const renamed = await createVendorsHttp().rename(1, 'New')

    // then: PATCH 경로와 본문이 맞고 새 이름이 반환된다
    expect(calls[0]).toMatchObject({ method: 'PATCH', path: '/api/v1/vendors/1', body: { name: 'New' } })
    expect(renamed.name).toBe('New')
  })

  // 삭제는 DELETE를 보내고 204를 성공으로 본다.
  // 테스트 코드: CL-091
  it('remove deletes and accepts 204', async () => {
    // given: 서버가 204를 돌려준다
    const { calls } = stubFetch(noContent())

    // when: id 1을 삭제한다
    await expect(createVendorsHttp().remove(1)).resolves.toBeUndefined()

    // then: 아무 값 없이 성공하고 DELETE를 보냈다
    expect(calls[0]).toMatchObject({ method: 'DELETE', path: '/api/v1/vendors/1' })
  })

  // Vendor 게이트웨이에는 Solution 관리 호출이 없다.
  // 테스트 코드: CL-091
  it('has no solution management calls', () => {
    // given: Vendor HTTP 어댑터를 만든다
    const vendors = createVendorsHttp()

    // when: Solution 관리 메서드를 찾는다
    for (const method of ['createSolution', 'renameSolution', 'removeSolution']) {
      // then: 세 메서드가 모두 없다
      expect(vendors).not.toHaveProperty(method)
    }
  })

  // 등록 실패(409·422·403)는 서버 문구를 그대로 담은 화면 kind로 던진다.
  // 테스트 코드: CL-091
  it.each([
    [409, 'already-exists', '이미 있는 Vendor 이름입니다.', 'conflict'],
    [409, 'invalid-state', '사용 중인 Vendor는 삭제할 수 없습니다. (Deal 2건)', 'conflict'],
    [422, 'invalid-value', 'Vendor 이름을 입력하세요.', 'validation'],
    [403, 'forbidden', '관리자 권한이 필요합니다', 'forbidden'],
  ])('failure %i "%s" keeps the server message', async (status, serverKind, detail, kind) => {
    // given: 서버가 해당 오류를 돌려준다
    stubFetch(problem(status, serverKind, detail))

    // when·then: Vendor를 등록한다 → 상태·kind가 맞고 서버 문구가 그대로다
    await expect(createVendorsHttp().create('x')).rejects.toMatchObject({ status, kind, message: detail })
  })

  // HTTP 게이트웨이가 vendors 어댑터를 노출한다.
  it('the http gateway exposes vendors', () => {
    // when: HTTP 게이트웨이를 만든다
    const result = createHttpGateway().vendors
    // then: vendors가 있다
    expect(result).toBeDefined()
  })
})
