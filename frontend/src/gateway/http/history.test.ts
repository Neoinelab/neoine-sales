import { afterEach, describe, expect, it, vi } from 'vitest'
import { CODE, serverHistory } from '../../test/fixtures/serverDeal'
import { createHistoryHttp } from './history'
import { json, problem, stubFetch } from './testHelpers'
import { USER_ID } from '../../test/fake/seed/ids'

afterEach(() => vi.unstubAllGlobals())

describe('history over HTTP', () => {
  // 구분이 없으면 쿼리 없이 이력을 읽는다.
  // 테스트 코드: DD-116
  it('reads GET /deals/{code}/history without a query when no category is chosen', async () => {
    // given: 구분 없음
    const { calls } = stubFetch(json([]))

    // when: 게이트웨이로 이력을 읽는다
    await createHistoryHttp().list(CODE, {})

    // then: GET 경로에 쿼리가 없다
    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/history` })
  })

  // 구분은 그대로 category 쿼리로 보낸다.
  // 테스트 코드: DD-116
  it('sends the category as it is', async () => {
    // given: 구분 expectedClose
    const { calls } = stubFetch(json([]))

    // when: 게이트웨이로 이력을 읽는다
    await createHistoryHttp().list(CODE, { category: 'expectedClose' })

    // then: 경로가 ?category=expectedClose다
    expect(calls[0]?.path).toBe(`/api/v1/deals/${CODE}/history?category=expectedClose`)
  })

  // 서버의 최신순을 유지하고 항목을 바꿔 돌려준다.
  // 테스트 코드: DD-116
  it('keeps the order of the server (newest first) and maps each entry', async () => {
    // given: 시각이 다른 서버 이력 두 건
    stubFetch(
      json([
        serverHistory({ id: 2, at: '2026-10-16T09:00:00+09:00', category: 'forecast', target: 'Forecast', before: 'Pipeline', after: 'Commit' }),
        serverHistory({ id: 1, at: '2026-10-15T09:00:00+09:00' }),
      ]),
    )

    // when: 게이트웨이로 이력을 읽는다
    const list = await createHistoryHttp().list(CODE, {})

    // then: id 순서가 서버와 같고 항목 필드가 매핑된다
    expect(list.map((h) => h.id)).toEqual([2, 1])
    expect(list[0]).toMatchObject({ dealCode: CODE, category: 'forecast', target: 'Forecast', before: 'Pipeline', after: 'Commit', by: { id: USER_ID.kim } })
  })

  // 없는 Deal의 이력은 404 오류다.
  // 테스트 코드: DD-116
  it('shows the 404 of an unknown deal', async () => {
    // given: 404 응답
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    // when·then: 이력을 읽는다 → status 404, kind not-found와 서버 문구다
    await expect(createHistoryHttp().list(CODE, {})).rejects.toMatchObject({ status: 404, kind: 'not-found', message: 'Deal을 찾을 수 없습니다.' })
  })

  // 모르는 구분의 422 오류를 보인다.
  // 테스트 코드: DD-116
  it('shows the 422 of an unknown category', async () => {
    // given: 422 응답
    stubFetch(problem(422, 'request-validation', '요청 형식이 올바르지 않습니다.'))

    // when·then: 이력을 읽는다 → status 422, kind validation이다
    await expect(createHistoryHttp().list(CODE, {})).rejects.toMatchObject({ status: 422, kind: 'validation' })
  })
})
