import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpGateway } from './index'
import { json, problem, stubFetch } from './testHelpers'
import { createTimeHttp } from './time'

afterEach(() => vi.unstubAllGlobals())

describe('server time over HTTP', () => {
  // GET /api/v1/time의 now·today를 그대로 돌려준다.
  // 테스트 코드: TM-029
  it('maps now and today from GET /api/v1/time', async () => {
    // given: 서버가 now·today를 준다
    const { calls } = stubFetch(json({ now: '2026-10-23T09:30:00.123456+09:00', today: '2026-10-23' }))

    // when: 서버 시각을 읽는다
    const time = await createTimeHttp().get()

    // then: GET /api/v1/time을 불렀고 같은 {now, today}를 돌려준다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/time' })
    expect(time).toEqual({ now: '2026-10-23T09:30:00.123456+09:00', today: '2026-10-23' })
  })

  // Z 표기는 그대로 돌려준다.
  // 테스트 코드: TM-029
  it('keeps a UTC offset written as Z', async () => {
    // given: 서버가 Z 표기 now를 준다
    stubFetch(json({ now: '2026-10-23T00:30:00Z', today: '2026-10-23' }))

    // when·then: now가 Z 그대로다
    expect((await createTimeHttp().get()).now).toBe('2026-10-23T00:30:00Z')
  })

  // 형식이 틀린 서버 시각 응답은 502 malformed-response다.
  // 테스트 코드: TM-030
  it.each([
    ['now without an offset', { now: '2026-10-23T09:30:00', today: '2026-10-23' }],
    ['now that is not a time', { now: 'yesterday', today: '2026-10-23' }],
    ['today that is not YYYY-MM-DD', { now: '2026-10-23T09:30:00+09:00', today: '2026/10/23' }],
    ['today with a time part', { now: '2026-10-23T09:30:00+09:00', today: '2026-10-23T00:00:00' }],
    ['a missing today', { now: '2026-10-23T09:30:00+09:00' }],
    ['a missing now', { today: '2026-10-23' }],
  ])('rejects a malformed body with %s', async (_name, body) => {
    // given: 형식이 틀린 서버 응답
    stubFetch(json(body))

    // when·then: 502 malformed-response로 reject된다
    await expect(createTimeHttp().get()).rejects.toMatchObject({ status: 502, kind: 'malformed-response' })
  })

  // 세션 없이 요청하면 401 ApiError를 그대로 넘긴다.
  // 테스트 코드: TM-031
  it('passes a 401 through as an ApiError', async () => {
    // given: 서버가 401을 준다
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    // when·then: 401 ApiError로 reject된다
    await expect(createTimeHttp().get()).rejects.toMatchObject({ status: 401 })
  })

  // HTTP 게이트웨이의 time도 같은 경로를 부른다.
  // 테스트 코드: TM-029
  it('is part of the http gateway', async () => {
    // given: 서버가 now·today를 준다
    const { calls } = stubFetch(json({ now: '2026-10-23T09:30:00+09:00', today: '2026-10-23' }))

    // when: createHttpGateway().time으로 읽는다
    await createHttpGateway().time.get()

    // then: /api/v1/time을 불렀다
    expect(calls[0]).toMatchObject({ path: '/api/v1/time' })
  })
})
