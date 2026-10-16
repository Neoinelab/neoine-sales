import { afterEach, describe, expect, it, vi } from 'vitest'
import { CODE, serverHistory } from '../../test/fixtures/serverDeal'
import { createHistoryHttp } from './history'
import { json, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

describe('history over HTTP', () => {
  it('reads GET /deals/{code}/history without a query when no category is chosen', async () => {
    const { calls } = stubFetch(json([]))

    await createHistoryHttp().list(CODE, {})

    expect(calls[0]).toMatchObject({ method: 'GET', path: `/api/v1/deals/${CODE}/history` })
  })

  it('sends the category as it is', async () => {
    const { calls } = stubFetch(json([]))

    await createHistoryHttp().list(CODE, { category: 'expectedClose' })

    expect(calls[0]?.path).toBe(`/api/v1/deals/${CODE}/history?category=expectedClose`)
  })

  it('keeps the order of the server (newest first) and maps each entry', async () => {
    stubFetch(
      json([
        serverHistory({ id: 'h2', at: '2026-10-16T09:00:00+09:00', category: 'forecast', target: 'Forecast', before: 'Pipeline', after: 'Commit' }),
        serverHistory({ id: 'h1', at: '2026-10-15T09:00:00+09:00' }),
      ]),
    )

    const list = await createHistoryHttp().list(CODE, {})

    expect(list.map((h) => h.id)).toEqual(['h2', 'h1'])
    expect(list[0]).toMatchObject({ dealCode: CODE, category: 'forecast', target: 'Forecast', before: 'Pipeline', after: 'Commit', by: { id: 'u-kim' } })
  })

  it('shows the 404 of an unknown deal', async () => {
    stubFetch(problem(404, 'not-found', 'Deal을 찾을 수 없습니다.'))

    await expect(createHistoryHttp().list(CODE, {})).rejects.toMatchObject({ status: 404, kind: 'not-found', message: 'Deal을 찾을 수 없습니다.' })
  })

  it('shows the 422 of an unknown category', async () => {
    stubFetch(problem(422, 'request-validation', '요청 형식이 올바르지 않습니다.'))

    await expect(createHistoryHttp().list(CODE, {})).rejects.toMatchObject({ status: 422, kind: 'validation' })
  })
})
