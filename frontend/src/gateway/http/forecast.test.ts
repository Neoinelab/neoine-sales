import { afterEach, describe, expect, it, vi } from 'vitest'
import { createForecastHttp } from './forecast'
import { createHttpGateway } from './index'
import { json, problem, stubFetch, userRefBody } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const query = (path: string) => new URL(path, 'http://localhost').searchParams

const COLUMNS = [
  { key: 'pipeline', name: 'Pipeline', outcome: 'open', order: 1 },
  { key: 'commit', name: '확정', outcome: 'open', order: 4 },
  { key: 'won', name: 'Won', outcome: 'won', order: 5 },
]

/** 서버 요약 응답(columns 순서와 cells 순서가 같다). */
function serverSummary(over: Record<string, unknown> = {}) {
  return {
    basis: 'live',
    as_of: '2026-10-21T14:03:00+09:00',
    snapshot_period: null,
    period: { year: 2026, quarter: 4, month: null, from: '2026-10-01', to: '2026-12-31' },
    columns: COLUMNS,
    rows: [
      {
        owner: userRefBody(7, '김영업', false, 'sales'),
        cells: [
          { key: 'pipeline', count: 2, amount: 150_000_000 },
          { key: 'commit', count: 1, amount: 7_000_000 },
          { key: 'won', count: 0, amount: 0 },
        ],
        open_total: { count: 3, amount: 157_000_000 },
      },
      {
        owner: userRefBody(9, '강퇴사', true, 'sales'),
        cells: [
          { key: 'pipeline', count: 1, amount: 3 },
          { key: 'commit', count: 0, amount: 0 },
          { key: 'won', count: 1, amount: 9 },
        ],
        open_total: { count: 1, amount: 3 },
      },
    ],
    total: {
      owner: null,
      cells: [
        { key: 'pipeline', count: 3, amount: 150_000_003 },
        { key: 'commit', count: 1, amount: 7_000_000 },
        { key: 'won', count: 1, amount: 9 },
      ],
      open_total: { count: 4, amount: 157_000_003 },
    },
    ...over,
  }
}

describe('forecast.summary over HTTP', () => {
  // 테스트 코드: FC-082
  it('다른 조건이 없으면 연도만 담아 GET /forecast/summary를 보낸다', async () => {
    // given: 서버 요약 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: 연도만 주고 요약을 읽는다
    await createForecastHttp().summary({ year: 2026 })

    // then: GET /api/v1/forecast/summary?year=2026이다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/forecast/summary?year=2026' })
  })

  // 테스트 코드: FC-082
  it('모든 조건을 snake_case 쿼리 키로 보낸다', async () => {
    // given: 서버 요약 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: 분기·Vendor·담당자를 주고 요약을 읽는다
    await createForecastHttp().summary({ year: 2026, quarter: 4, vendorId: 6, ownerId: 7 })

    // then: year·quarter·vendor_id·owner_user_id가 쿼리에 담긴다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({
      year: '2026',
      quarter: '4',
      vendor_id: '6',
      owner_user_id: '7',
    })
  })

  // 테스트 코드: FC-082
  it('월 조건이면 분기 대신 month를 보낸다', async () => {
    // given: 월 기간의 서버 요약 응답
    const { calls } = stubFetch(json(serverSummary({ period: { year: 2026, quarter: null, month: 3, from: '2026-03-01', to: '2026-03-31' } })))

    // when: 월 조건으로 요약을 읽는다
    await createForecastHttp().summary({ year: 2026, month: 3 })

    // then: 쿼리에 year와 month만 있다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ year: '2026', month: '3' })
  })

  // 테스트 코드: FC-082
  it('비어 있는 조건은 보내지 않는다', async () => {
    // given: 서버 요약 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: undefined 조건을 주고 요약을 읽는다
    await createForecastHttp().summary({ year: 2026, quarter: undefined, vendorId: undefined, ownerId: undefined })

    // then: quarter·vendor_id·owner_user_id가 쿼리에 없다
    expect(query(calls[0]?.path ?? '').has('quarter')).toBe(false)
    expect(query(calls[0]?.path ?? '').has('vendor_id')).toBe(false)
    expect(query(calls[0]?.path ?? '').has('owner_user_id')).toBe(false)
  })

  // 테스트 코드: FC-082
  it('열을 order·outcome과 함께 옮긴다', async () => {
    // given: 서버 요약 응답
    stubFetch(json(serverSummary()))

    // when: 요약을 읽는다
    const summary = await createForecastHttp().summary({ year: 2026, quarter: 4 })

    // then: 열이 {key, name, outcome, order}다
    expect(summary.columns).toEqual(COLUMNS)
  })

  // 테스트 코드: FC-082
  it('셀 목록을 key별 레코드로 바꾸고 담당자 라벨을 이름으로 쓴다', async () => {
    // given: 서버 요약 응답(퇴사자 행 포함)
    stubFetch(json(serverSummary()))

    // when: 요약을 읽는다
    const summary = await createForecastHttp().summary({ year: 2026, quarter: 4 })

    // then: 행의 id·이름(퇴사 라벨 포함)과 key별 셀·Open 합계가 맞다
    expect(summary.rows.map((r) => [r.ownerId, r.ownerName])).toEqual([
      [7, '김영업'],
      [9, '강퇴사(퇴사)'],
    ])
    expect(summary.rows[0]?.cells).toEqual({
      pipeline: { count: 2, amount: 150_000_000 },
      commit: { count: 1, amount: 7_000_000 },
      won: { count: 0, amount: 0 },
    })
    expect(summary.rows[0]?.total).toEqual({ count: 3, amount: 157_000_000 })
  })

  // 테스트 코드: FC-082
  it('합계 행은 담당자 없이 "합계"로 옮긴다', async () => {
    // given: 서버 요약 응답
    stubFetch(json(serverSummary()))

    // when: 요약을 읽는다
    const { totalRow } = await createForecastHttp().summary({ year: 2026, quarter: 4 })

    // then: ownerId null, 이름 "합계", 합계 셀이 맞다
    expect(totalRow).toMatchObject({ ownerId: null, ownerName: '합계', total: { count: 4, amount: 157_000_003 } })
    expect(totalRow.cells.pipeline).toEqual({ count: 3, amount: 150_000_003 })
  })

  // 테스트 코드: FC-082
  it('basis·기준 시각을 유지하고 보낸 조건을 되돌려 준다', async () => {
    // given: 서버 요약 응답
    stubFetch(json(serverSummary()))

    // when: 담당자 조건으로 요약을 읽는다
    const summary = await createForecastHttp().summary({ year: 2026, quarter: 4, ownerId: 7 })

    // then: basis live, 기준 시각, 보낸 조건이 담긴다
    expect(summary.basis).toBe('live')
    expect(summary.asOf).toBe('2026-10-21T14:03:00+09:00')
    expect(summary.query).toEqual({ year: 2026, quarter: 4, ownerId: 7 })
  })

  // 테스트 코드: FC-082
  it('서버가 행을 주지 않으면 행이 없다', async () => {
    // given: 행이 없는 서버 응답
    stubFetch(json(serverSummary({ rows: [] })))

    // when: 요약을 읽는다
    const summary = await createForecastHttp().summary({ year: 2031 })

    // then: 행이 비어 있다
    expect(summary.rows).toEqual([])
  })

  // 테스트 코드: FC-082
  it('422 invalid-value는 ApiError로 전달한다', async () => {
    // given: 422 invalid-value 응답
    stubFetch(problem(422, 'invalid-value', 'Quarter와 월은 함께 선택할 수 없습니다.'))

    // when·then: 요약을 읽으면 상태 422와 서버 문구의 ApiError가 reject된다
    await expect(createForecastHttp().summary({ year: 2026, quarter: 1, month: 1 })).rejects.toMatchObject({
      status: 422,
      message: 'Quarter와 월은 함께 선택할 수 없습니다.',
    })
  })

  // 테스트 코드: FC-082
  it('401은 그대로 전달한다', async () => {
    // given: 401 응답
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    // when·then: 요약을 읽으면 상태 401이 reject된다
    await expect(createForecastHttp().summary({ year: 2026 })).rejects.toMatchObject({ status: 401 })
  })

  // 테스트 코드: FC-082
  it('HTTP 게이트웨이에 연결돼 있다 (501 스텁이 아니다)', async () => {
    // given: 서버 요약 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: HTTP 게이트웨이로 요약을 읽는다
    await createHttpGateway().forecast.summary({ year: 2026 })

    // then: 요약 경로로 한 번 요청한다
    expect(calls).toHaveLength(1)
    expect(calls[0]?.path).toBe('/api/v1/forecast/summary?year=2026')
  })
})
