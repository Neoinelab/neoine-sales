import { afterEach, describe, expect, it, vi } from 'vitest'
import { createDashboardHttp } from './dashboard'
import { createHttpGateway } from './index'
import { json, problem, stubFetch } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const query = (path: string) => new URL(path, 'http://localhost').searchParams

const COLUMNS = [
  { key: 'pipeline', name: 'Pipeline', outcome: 'open', order: 1 },
  { key: 'commit', name: '확정', outcome: 'open', order: 4 },
  { key: 'won', name: 'Won', outcome: 'won', order: 5 },
]

/** 서버 요약 응답(DSH-R3 응답 예시 모양). cells는 columns와 같은 순서의 목록이다. */
function serverSummary(over: Record<string, unknown> = {}) {
  return {
    as_of: '2026-10-23T09:00:00+09:00',
    today: '2026-10-23',
    period: { year: 2026, quarter: null, quarters: [], from: '2026-01-01', to: '2026-12-31' },
    forecasts: {
      columns: COLUMNS,
      cells: [
        { key: 'pipeline', count: 18, amount: 320_000_000 },
        { key: 'commit', count: 3, amount: 70_000_000 },
        { key: 'won', count: 2, amount: 40_000_000 },
      ],
      open_total: { count: 21, amount: 390_000_000 },
    },
    statuses: {
      items: [
        { key: 'prospecting', name: '기회발굴', order: 1, count: 18, amount: 320_000_000 },
        { key: 'contract_completed', name: '계약완료', order: 7, count: 2, amount: 40_000_000 },
      ],
      total: { count: 20, amount: 360_000_000 },
    },
    quarters: [1, 2, 3, 4].map((quarter) => ({
      quarter,
      from: `2026-${String(quarter * 3 - 2).padStart(2, '0')}-01`,
      to: ['2026-03-31', '2026-06-30', '2026-09-30', '2026-12-31'][quarter - 1],
      cells: [
        { key: 'pipeline', count: quarter, amount: quarter * 10 },
        { key: 'commit', count: 0, amount: 0 },
        { key: 'won', count: 1, amount: 5 },
      ],
      open_total: { count: quarter, amount: quarter * 10 },
      total: { count: quarter + 1, amount: quarter * 10 + 5 },
    })),
    attention: {
      stale_days: 14,
      overdue: 4,
      stale: 5,
      closing_this_month: { year: 2026, month: 10, count: 4 },
      closing_this_quarter: { year: 2026, quarter: 4, count: 7 },
    },
    ...over,
  }
}

describe('dashboard.summary over HTTP', () => {
  // 테스트 코드: DSH-056
  it('다른 조건이 없으면 연도만 담아 GET /dashboard/summary를 보낸다', async () => {
    // given: 가짜 서버 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: 연도만 주고 조회한다
    await createDashboardHttp().summary({ year: 2026 })

    // then: 쿼리는 year뿐이다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/dashboard/summary?year=2026' })
  })

  // 테스트 코드: DSH-056
  it('모든 조건을 snake_case 쿼리 키로 바꾼다', async () => {
    // given: 가짜 서버 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: 연도·분기·담당자·Vendor를 주고 조회한다
    await createDashboardHttp().summary({ year: 2026, quarters: [4], ownerId: 7, vendorId: 6 })

    // then: year·quarter·owner_user_id·vendor_id 정수 값이다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({
      year: '2026',
      quarter: '4',
      owner_user_id: '7',
      vendor_id: '6',
    })
  })

  // 테스트 코드: DSH-056
  it('빈 조건은 보내지 않고 월은 절대 보내지 않는다', async () => {
    // given: 가짜 서버 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: 비어 있는 조건을 주고 조회한다
    await createDashboardHttp().summary({ year: 2026, quarters: undefined, ownerId: undefined, vendorId: undefined })
    const sent = query(calls[0]?.path ?? '')
    // then: 쿼리 키는 year뿐이다
    expect([...sent.keys()]).toEqual(['year'])
  })

  // 테스트 코드: DSH-056
  it('기준 시각·업무 날짜·기간을 그대로 둔다', async () => {
    // given: 가짜 서버 응답
    stubFetch(json(serverSummary()))

    // when: 조회한다
    const summary = await createDashboardHttp().summary({ year: 2026 })

    // then: asOf·today·period가 응답 그대로다
    expect(summary.asOf).toBe('2026-10-23T09:00:00+09:00')
    expect(summary.today).toBe('2026-10-23')
    expect(summary.period).toEqual({ year: 2026, quarter: null, quarters: [], from: '2026-01-01', to: '2026-12-31' })
  })

  // 테스트 코드: DSH-056
  it('Forecast 열을 옮기고 셀 목록을 key별 Record로 바꾼다', async () => {
    // given: 가짜 서버 응답
    stubFetch(json(serverSummary()))

    // when: 조회한다
    const { forecast } = await createDashboardHttp().summary({ year: 2026 })

    // then: 열은 그대로이고 셀은 key별 Record, Open 합계가 있다
    expect(forecast.columns).toEqual(COLUMNS)
    expect(forecast.cells).toEqual({
      pipeline: { count: 18, amount: 320_000_000 },
      commit: { count: 3, amount: 70_000_000 },
      won: { count: 2, amount: 40_000_000 },
    })
    expect(forecast.openTotal).toEqual({ count: 21, amount: 390_000_000 })
  })

  // 테스트 코드: DSH-056
  it('서버가 셀을 주지 않은 열은 0으로 채운다', async () => {
    // given: commit 셀이 빠진 서버 응답
    const body = serverSummary()
    body.forecasts.cells = body.forecasts.cells.filter((c) => c.key !== 'commit')
    stubFetch(json(body))

    // when: 조회한다
    const { forecast } = await createDashboardHttp().summary({ year: 2026 })

    // then: commit 셀이 0건·0원이다
    expect(forecast.cells.commit).toEqual({ count: 0, amount: 0 })
  })

  // 테스트 코드: DSH-056
  it('Status 항목을 서버 순서로 옮기고 합계를 둔다', async () => {
    // given: 가짜 서버 응답
    stubFetch(json(serverSummary()))

    // when: 조회한다
    const { statuses } = await createDashboardHttp().summary({ year: 2026 })

    // then: 항목은 서버 순서이고 합계가 있다
    expect(statuses.items).toEqual([
      { key: 'prospecting', name: '기회발굴', order: 1, count: 18, amount: 320_000_000 },
      { key: 'contract_completed', name: '계약완료', order: 7, count: 2, amount: 40_000_000 },
    ])
    expect(statuses.total).toEqual({ count: 20, amount: 360_000_000 })
  })

  // 테스트 코드: DSH-056
  it('네 분기를 범위·셀 Record·Open 합계·합계와 함께 옮긴다', async () => {
    // given: 가짜 서버 응답
    stubFetch(json(serverSummary()))

    // when: 조회한다
    const { quarters } = await createDashboardHttp().summary({ year: 2026 })

    // then: Q1~Q4 행이고 Q4 행이 화면 모양이다
    expect(quarters.map((q) => q.quarter)).toEqual([1, 2, 3, 4])
    expect(quarters[3]).toEqual({
      quarter: 4,
      from: '2026-10-01',
      to: '2026-12-31',
      cells: { pipeline: { count: 4, amount: 40 }, commit: { count: 0, amount: 0 }, won: { count: 1, amount: 5 } },
      openTotal: { count: 4, amount: 40 },
      total: { count: 5, amount: 45 },
    })
  })

  // 테스트 코드: DSH-056
  it('주의 블록을 camelCase로 옮긴다', async () => {
    // given: 가짜 서버 응답
    stubFetch(json(serverSummary()))

    // when: 조회한다
    const { attention } = await createDashboardHttp().summary({ year: 2026 })

    // then: staleDays·closingThisMonth 등 화면 모양이다
    expect(attention).toEqual({
      staleDays: 14,
      overdue: 4,
      stale: 5,
      closingThisMonth: { year: 2026, month: 10, count: 4 },
      closingThisQuarter: { year: 2026, quarter: 4, count: 7 },
    })
  })

  // 테스트 코드: DSH-056
  it('고른 분기 하나를 기간에 그대로 둔다', async () => {
    // given: Q3 기간의 서버 응답
    stubFetch(json(serverSummary({ period: { year: 2026, quarter: 3, quarters: [3], from: '2026-07-01', to: '2026-09-30' } })))

    // when: Q3로 조회한다
    const { period } = await createDashboardHttp().summary({ year: 2026, quarters: [3] })

    // then: 기간에 quarter 3, quarters [3]이 있다
    expect(period).toEqual({ year: 2026, quarter: 3, quarters: [3], from: '2026-07-01', to: '2026-09-30' })
  })

  // 테스트 코드: DSH-056
  it('고른 분기마다 quarter 키를 반복한다', async () => {
    // given: 가짜 서버 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: Q1·Q3로 조회한다
    await createDashboardHttp().summary({ year: 2026, quarters: [1, 3] })

    // then: quarter가 1, 3으로 반복된다
    expect(query(calls[0]?.path ?? '').getAll('quarter')).toEqual(['1', '3'])
  })

  // 테스트 코드: DSH-056
  it('빈 분기 목록은 quarter 키를 보내지 않는다', async () => {
    // given: 가짜 서버 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: 빈 분기 목록으로 조회한다
    await createDashboardHttp().summary({ year: 2026, quarters: [] })

    // then: quarter 키가 없다
    expect(query(calls[0]?.path ?? '').has('quarter')).toBe(false)
  })

  // 테스트 코드: DSH-056
  it('여러 분기를 기간에 옮긴다', async () => {
    // given: Q1·Q3 기간의 서버 응답
    stubFetch(json(serverSummary({ period: { year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' } })))

    // when: Q1·Q3로 조회한다
    const { period } = await createDashboardHttp().summary({ year: 2026, quarters: [1, 3] })

    // then: quarter는 null, quarters는 [1, 3]이다
    expect(period).toEqual({ year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' })
  })

  // 테스트 코드: DSH-056
  it.each([[[0]], [[5]], [[1, 7]]])('기간의 분기 %j은 형식이 틀린 응답으로 거절한다', async (quarters) => {
    // given: 분기가 1~4 밖인 서버 응답
    stubFetch(json(serverSummary({ period: { year: 2026, quarter: null, quarters, from: '2026-01-01', to: '2026-12-31' } })))

    // when·then: 조회하면 malformed-response 오류다
    await expect(createDashboardHttp().summary({ year: 2026 })).rejects.toMatchObject({ kind: 'malformed-response' })
  })

  // 테스트 코드: DSH-056
  it('422 request-validation 문제를 ApiError로 호출자에게 넘긴다', async () => {
    // given: 서버가 422 request-validation으로 답한다
    stubFetch(problem(422, 'request-validation', '요청 값이 올바르지 않습니다.'))

    // when·then: 조회하면 상태 422와 서버 문구의 ApiError다
    await expect(createDashboardHttp().summary({ year: 1899 })).rejects.toMatchObject({
      status: 422,
      message: '요청 값이 올바르지 않습니다.',
    })
  })

  // 테스트 코드: DSH-056
  it('401을 호출자에게 넘긴다', async () => {
    // given: 서버가 401로 답한다
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    // when·then: 조회하면 상태 401의 ApiError다
    await expect(createDashboardHttp().summary({ year: 2026 })).rejects.toMatchObject({ status: 401 })
  })

  // 테스트 코드: DSH-056
  it('HTTP 게이트웨이에 연결되어 있다', async () => {
    // given: 가짜 서버 응답
    const { calls } = stubFetch(json(serverSummary()))

    // when: HTTP 게이트웨이로 조회한다
    await createHttpGateway().dashboard.summary({ year: 2026 })

    // then: 요청 하나가 요약 경로로 간다
    expect(calls).toHaveLength(1)
    expect(calls[0]?.path).toBe('/api/v1/dashboard/summary?year=2026')
  })
})
