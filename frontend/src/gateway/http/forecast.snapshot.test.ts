import { afterEach, describe, expect, it, vi } from 'vitest'
import { createForecastHttp } from './forecast'
import { createHttpGateway } from './index'
import { json, problem, stubFetch, userRefBody } from './testHelpers'

afterEach(() => vi.unstubAllGlobals())

const query = (path: string) => new URL(path, 'http://localhost').searchParams

const TAKEN_AT = '2026-10-01T00:05:00+09:00'
const COLUMNS = [
  { key: 'pipeline', name: 'Pipeline', outcome: 'open', order: 1 },
  { key: 'commit', name: '확정(당시)', outcome: 'open', order: 4 },
  { key: 'won', name: 'Won', outcome: 'won', order: 5 },
]

/** 서버 스냅숏 요약 응답(실시간 요약과 같은 모양, basis=snapshot, as_of=생성 시각). */
function serverSnapshotSummary(over: Record<string, unknown> = {}) {
  return {
    basis: 'snapshot',
    as_of: TAKEN_AT,
    snapshot_period: '2026-09',
    period: { year: 2026, quarter: 3, month: null, from: '2026-07-01', to: '2026-09-30' },
    columns: COLUMNS,
    rows: [
      {
        owner: userRefBody(7, '김영업', false, 'sales'),
        cells: [
          { key: 'pipeline', count: 2, amount: 200_000_000 },
          { key: 'commit', count: 1, amount: 50_000_000 },
          { key: 'won', count: 1, amount: 700_000_000 },
        ],
        open_total: { count: 3, amount: 250_000_000 },
      },
    ],
    total: {
      owner: null,
      cells: [
        { key: 'pipeline', count: 2, amount: 200_000_000 },
        { key: 'commit', count: 1, amount: 50_000_000 },
        { key: 'won', count: 1, amount: 700_000_000 },
      ],
      open_total: { count: 3, amount: 250_000_000 },
    },
    ...over,
  }
}

describe('forecast.snapshots over HTTP', () => {
  // 테스트 코드: FC-083
  it('쿼리 없이 GET /forecast/snapshots를 보낸다', async () => {
    // given: 빈 목록 응답
    const { calls } = stubFetch(json({ items: [] }))

    // when: 스냅숏 목록을 읽는다
    await createForecastHttp().snapshots()

    // then: GET /api/v1/forecast/snapshots다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/forecast/snapshots' })
  })

  // 테스트 코드: FC-083
  it('항목을 period·takenAt으로 옮기고 서버 순서를 유지한다', async () => {
    // given: 최근 순 목록 응답
    stubFetch(
      json({
        items: [
          { period: '2026-09', taken_at: TAKEN_AT },
          { period: '2026-08', taken_at: '2026-09-01T00:05:00+09:00' },
        ],
      }),
    )

    // when: 스냅숏 목록을 읽는다
    const list = await createForecastHttp().snapshots()

    // then: 서버 순서 그대로 period·takenAt이다
    expect(list).toEqual([
      { period: '2026-09', takenAt: TAKEN_AT },
      { period: '2026-08', takenAt: '2026-09-01T00:05:00+09:00' },
    ])
  })

  // 테스트 코드: FC-083
  it('저장된 것이 없으면 빈 목록이다', async () => {
    // given: 빈 목록 응답
    stubFetch(json({ items: [] }))

    // when·then: 목록을 읽으면 비어 있다
    expect(await createForecastHttp().snapshots()).toEqual([])
  })

  // 테스트 코드: FC-083
  it('401은 그대로 전달한다', async () => {
    // given: 401 응답
    stubFetch(problem(401, 'unauthenticated', '로그인이 필요합니다.'))

    // when·then: 목록을 읽으면 상태 401이 reject된다
    await expect(createForecastHttp().snapshots()).rejects.toMatchObject({ status: 401 })
  })
})

describe('forecast.snapshotSummary over HTTP', () => {
  // 테스트 코드: FC-083
  it('경로에 기준 월을 넣고 다른 조건이 없으면 연도만 보낸다', async () => {
    // given: 스냅숏 요약 응답
    const { calls } = stubFetch(json(serverSnapshotSummary()))

    // when: 기준 월과 연도로 요약을 읽는다
    await createForecastHttp().snapshotSummary('2026-09', { year: 2026 })

    // then: GET /api/v1/forecast/snapshots/2026-09/summary?year=2026이다
    expect(calls[0]).toMatchObject({ method: 'GET', path: '/api/v1/forecast/snapshots/2026-09/summary?year=2026' })
  })

  // 테스트 코드: FC-083
  it('연도·분기·담당자를 snake_case 쿼리 키로 보낸다', async () => {
    // given: 스냅숏 요약 응답
    const { calls } = stubFetch(json(serverSnapshotSummary()))

    // when: 분기·담당자를 주고 요약을 읽는다
    await createForecastHttp().snapshotSummary('2026-09', { year: 2026, quarter: 3, ownerId: 7 })

    // then: year·quarter·owner_user_id가 쿼리에 담긴다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ year: '2026', quarter: '3', owner_user_id: '7' })
  })

  // 테스트 코드: FC-083
  it('월 조건이면 분기 대신 month를 보낸다', async () => {
    // given: 스냅숏 요약 응답
    const { calls } = stubFetch(json(serverSnapshotSummary()))

    // when: 월 조건으로 요약을 읽는다
    await createForecastHttp().snapshotSummary('2026-09', { year: 2026, month: 8 })

    // then: 쿼리에 year와 month만 있다
    expect(Object.fromEntries(query(calls[0]?.path ?? ''))).toEqual({ year: '2026', month: '8' })
  })

  // 테스트 코드: FC-083
  it('호출자가 Vendor를 넘겨도 보내지 않는다 (스냅숏에는 Vendor가 없다)', async () => {
    // given: 스냅숏 요약 응답과 Vendor를 담은 조건
    const { calls } = stubFetch(json(serverSnapshotSummary()))
    const withVendor = { year: 2026, vendorId: 6 } as { year: number }

    // when: 그 조건으로 요약을 읽는다
    await createForecastHttp().snapshotSummary('2026-09', withVendor)

    // then: 쿼리에 vendor_id가 없다
    expect(query(calls[0]?.path ?? '').has('vendor_id')).toBe(false)
  })

  // 테스트 코드: FC-083
  it('basis·기준 월·생성 시각(asOf)을 옮긴다', async () => {
    // given: 스냅숏 요약 응답
    stubFetch(json(serverSnapshotSummary()))

    // when: 요약을 읽는다
    const summary = await createForecastHttp().snapshotSummary('2026-09', { year: 2026, quarter: 3 })

    // then: basis snapshot, 기준 월, asOf는 생성 시각, 보낸 조건이 담긴다
    expect(summary.basis).toBe('snapshot')
    expect(summary.snapshotPeriod).toBe('2026-09')
    expect(summary.asOf).toBe(TAKEN_AT)
    expect(summary.query).toEqual({ year: 2026, quarter: 3 })
  })

  // 테스트 코드: FC-083
  it('저장된 열·행·합계 행을 실시간 요약처럼 옮긴다', async () => {
    // given: 스냅숏 요약 응답
    stubFetch(json(serverSnapshotSummary()))

    // when: 요약을 읽는다
    const summary = await createForecastHttp().snapshotSummary('2026-09', { year: 2026, quarter: 3 })

    // then: 열·행·합계 행이 화면 모양이다
    expect(summary.columns).toEqual(COLUMNS)
    expect(summary.rows.map((r) => [r.ownerId, r.ownerName])).toEqual([[7, '김영업']])
    expect(summary.rows[0]?.cells.commit).toEqual({ count: 1, amount: 50_000_000 })
    expect(summary.rows[0]?.total).toEqual({ count: 3, amount: 250_000_000 })
    expect(summary.totalRow).toMatchObject({ ownerId: null, ownerName: '합계', total: { count: 3, amount: 250_000_000 } })
  })

  // 테스트 코드: FC-082
  it('실시간 요약에는 기준 월이 없다', async () => {
    // given: basis live 응답
    stubFetch(json(serverSnapshotSummary({ basis: 'live', snapshot_period: null, as_of: '2026-10-21T14:03:00+09:00' })))

    // when: 실시간 요약을 읽는다
    const summary = await createForecastHttp().summary({ year: 2026, quarter: 3 })

    // then: 기준 월이 null이다
    expect(summary.basis).toBe('live')
    expect(summary.snapshotPeriod).toBeNull()
  })

  // 테스트 코드: FC-083
  it('없는 기준 월의 404는 ApiError로 전달한다', async () => {
    // given: 404 응답
    stubFetch(problem(404, 'not-found', '해당 기준 월의 스냅숏이 없습니다.'))

    // when·then: 요약을 읽으면 상태 404와 서버 문구가 reject된다
    await expect(createForecastHttp().snapshotSummary('2025-01', { year: 2026 })).rejects.toMatchObject({
      status: 404,
      message: '해당 기준 월의 스냅숏이 없습니다.',
    })
  })

  // 테스트 코드: FC-083
  it('422는 그대로 전달한다', async () => {
    // given: 422 응답
    stubFetch(problem(422, 'invalid-value', 'Quarter와 월은 함께 선택할 수 없습니다.'))

    // when·then: 요약을 읽으면 상태 422가 reject된다
    await expect(createForecastHttp().snapshotSummary('2026-09', { year: 2026, quarter: 1, month: 1 })).rejects.toMatchObject({
      status: 422,
    })
  })

  // 테스트 코드: FC-083
  it('HTTP 게이트웨이에 연결돼 있다', async () => {
    // given: 목록과 요약 응답
    const { calls } = stubFetch(json({ items: [] }), json(serverSnapshotSummary()))
    const gateway = createHttpGateway()

    // when: 목록과 요약을 읽는다
    await gateway.forecast.snapshots()
    await gateway.forecast.snapshotSummary('2026-09', { year: 2026 })

    // then: 두 경로로 차례로 요청한다
    expect(calls.map((c) => c.path)).toEqual([
      '/api/v1/forecast/snapshots',
      '/api/v1/forecast/snapshots/2026-09/summary?year=2026',
    ])
  })
})
