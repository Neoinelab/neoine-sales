// @vitest-environment node
// Blob 응답을 실제 바이트로 확인하려면 undici Response가 필요해 이 파일만 node 환경에서 돌린다(attachments.test.ts와 같다).
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.hoisted(() => {
  Object.assign(globalThis, { window: { location: { origin: 'http://localhost:5173' } } })
})

import { createDealsHttp } from './deals'
import { problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const DISPOSITION = `attachment; filename="Deals_20261015.csv"; filename*=UTF-8''Deals_20261015.csv`
const BOM_CSV = new Uint8Array([0xef, 0xbb, 0xbf, 0x44, 0x65, 0x61, 0x6c, 0x0d, 0x0a])

function csv(headers: Record<string, string> = { 'Content-Disposition': DISPOSITION }): Response {
  return new Response(BOM_CSV, { status: 200, headers: { 'Content-Type': 'text/csv; charset=utf-8', ...headers } })
}

describe('deals.exportCsv over HTTP', () => {
  // 목록 쿼리에서 offset·limit을 빼고 같은 snake_case 키로 보내고 Blob과 파일 이름을 돌려준다
  // 테스트 코드: DL-123
  it('sends the list query without offset and limit and returns the blob with the file name', async () => {
    // given: 서버가 파일 이름 헤더와 CSV 본문으로 답한다
    const { calls } = stubFetch(csv())

    // when: 페이지 정보가 든 목록 조건으로 exportCsv를 부른다
    const file = await createDealsHttp().exportCsv({
      statusKey: 'a',
      forecastKeys: ['best', 'commit'],
      quarters: [1, 3],
      mine: true,
      nextActionStatus: 'notDone',
      sort: 'revenueAmount',
      order: 'asc',
      offset: 20,
      limit: 20,
    })

    // then: GET /api/v1/deals/export이고 쿼리는 목록과 같은 키이며 offset·limit이 없다
    expect(calls[0]?.method).toBe('GET')
    const url = new URL(calls[0]?.path ?? '', 'http://localhost')
    expect(url.pathname).toBe('/api/v1/deals/export')
    expect(url.searchParams.get('status_key')).toBe('a')
    expect(url.searchParams.getAll('forecast_key')).toEqual(['best', 'commit'])
    expect(url.searchParams.getAll('quarter')).toEqual(['1', '3'])
    expect(url.searchParams.get('mine')).toBe('true')
    expect(url.searchParams.get('next_action_status')).toBe('not_done')
    expect(url.searchParams.get('sort')).toBe('revenue_amount')
    expect(url.searchParams.get('order')).toBe('asc')
    expect(url.searchParams.has('offset')).toBe(false)
    expect(url.searchParams.has('limit')).toBe(false)
    // then: 파일 이름은 응답 헤더에서, 본문은 바이트 그대로의 Blob이다
    expect(file.fileName).toBe('Deals_20261015.csv')
    expect(file.blob).toBeInstanceOf(Blob)
    expect(Array.from(new Uint8Array(await file.blob.arrayBuffer()))).toEqual(Array.from(BOM_CSV))
  })

  // 조건이 없으면 쿼리도 비어 있다
  // 테스트 코드: DL-123
  it('sends no query at all for an empty condition', async () => {
    // given: 서버가 CSV로 답한다
    const { calls } = stubFetch(csv())

    // when: 조건 없이 exportCsv를 부른다
    await createDealsHttp().exportCsv({})

    // then: 경로만 있고 쿼리가 없다
    expect(calls[0]?.path).toBe('/api/v1/deals/export')
  })

  // 422 응답은 서버 문구의 오류로 거절된다
  // 테스트 코드: DL-123
  it('rejects with the server message on a 422', async () => {
    // given: 상한 초과 문제 응답
    const detail = '내려받을 Deal이 10,000건을 넘습니다(10,001건). 조건을 좁혀 다시 시도하세요.'
    stubFetch(problem(422, 'invalid-value', detail))

    // when·then: exportCsv는 상태·서버 문구가 담긴 오류로 거절된다
    await expect(createDealsHttp().exportCsv({})).rejects.toMatchObject({ status: 422, message: detail })
  })
})
