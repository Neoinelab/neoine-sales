import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpGateway } from './index'
import { json, problem, stubFetch } from './testHelpers'
import { createTimeHttp } from './time'

afterEach(() => vi.unstubAllGlobals())

describe('server time over HTTP', () => {
  it('maps now and today from GET /api/v1/time', async () => {
    const { calls } = stubFetch(json({ now: '2026-10-23T09:30:00.123456+09:00', today: '2026-10-23' }))

    const time = await createTimeHttp().get()

    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/time' })
    expect(time).toEqual({ now: '2026-10-23T09:30:00.123456+09:00', today: '2026-10-23' })
  })

  it('keeps a UTC offset written as Z', async () => {
    stubFetch(json({ now: '2026-10-23T00:30:00Z', today: '2026-10-23' }))

    expect((await createTimeHttp().get()).now).toBe('2026-10-23T00:30:00Z')
  })

  it.each([
    ['now without an offset', { now: '2026-10-23T09:30:00', today: '2026-10-23' }],
    ['now that is not a time', { now: 'yesterday', today: '2026-10-23' }],
    ['today that is not YYYY-MM-DD', { now: '2026-10-23T09:30:00+09:00', today: '2026/10/23' }],
    ['today with a time part', { now: '2026-10-23T09:30:00+09:00', today: '2026-10-23T00:00:00' }],
    ['a missing today', { now: '2026-10-23T09:30:00+09:00' }],
    ['a missing now', { today: '2026-10-23' }],
  ])('rejects a malformed body with %s', async (_name, body) => {
    stubFetch(json(body))

    await expect(createTimeHttp().get()).rejects.toMatchObject({ status: 502, kind: 'malformed-response' })
  })

  it('passes a 401 through as an ApiError', async () => {
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    await expect(createTimeHttp().get()).rejects.toMatchObject({ status: 401 })
  })

  it('is part of the http gateway', async () => {
    const { calls } = stubFetch(json({ now: '2026-10-23T09:30:00+09:00', today: '2026-10-23' }))

    await createHttpGateway().time.get()

    expect(calls[0]).toMatchObject({ path: '/api/v1/time' })
  })
})
