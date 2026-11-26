import { describe, expect, it } from 'vitest'
import type { ReportQueryInput, ReportResult } from '../../../shared/model/reportTypes'
import { invalidReport, reportTimeout } from '../errors'
import { REPORT_CATALOG } from '../seed/reportCatalog'
import { expectApiError, mockAs } from '../testing'

/** Reports Fake 자체의 규칙(계약 스위트가 다루지 않는 제어 도구, 위반 흉내와 합성 결과). */

const CODE_ONLY: ReportQueryInput = {
  columns: [{ field: 'deal.code', group: false }],
  conditions: [],
  combine: 'and',
  rowLimit: 100,
}

const CANNED: ReportResult = {
  rowScope: 'deal',
  actionFilter: 'none',
  dealNumbersOnce: false,
  columns: [
    { index: 0, field: 'deal.code', label: 'Deal code', entity: 'deal', type: 'text', valueType: 'text', format: null, unit: null, prefixLength: null, group: false, aggregate: null },
  ],
  rows: [['20261016-0001']],
  totals: null,
  totalCount: 1,
  truncated: false,
  rowLimit: 100,
  sql: 'SELECT demo',
  elapsedMs: 5,
  today: '2026-10-15',
}

describe('reports Fake', () => {
  // 테스트 코드: RQ-107
  it('필드 카탈로그의 사본을 주며 호출자가 바꿔도 원본은 그대로다', async () => {
    // given: 로그인한 Fake 게이트웨이
    const { gateway } = await mockAs('kim')

    // when: 카탈로그를 읽어 필드를 비우고 다시 읽는다
    const first = await gateway.reports.fields()
    const originalLength = first.fields.length
    first.fields.length = 0
    const second = await gateway.reports.fields()

    // then: 다시 읽은 카탈로그와 원본에 처음 필드가 모두 남아 있다
    expect(originalLength).toBeGreaterThan(0)
    expect(second.fields).toHaveLength(originalLength)
    expect(REPORT_CATALOG.fields).toHaveLength(originalLength)
  })

  // 테스트 코드: RQ-106
  it('처리기 결과를 답하고 요청을 모두 기록한다', async () => {
    // given: 정해진 결과를 돌려주는 처리기
    const mock = await mockAs('kim')
    mock.control.setReportQueryHandler(() => CANNED)

    // when: 조회한다
    const result = await mock.gateway.reports.query(CODE_ONLY)

    // then: 처리기 결과가 그대로이고 요청이 기록된다
    expect(result.rows).toEqual([['20261016-0001']])
    expect(mock.control.reportQueries()).toEqual([CODE_ONLY])
  })

  // 테스트 코드: RQ-106
  it('처리기가 던진 오류로 거절한다', async () => {
    // given: 시간 초과를 던지는 처리기
    const mock = await mockAs('kim')
    mock.control.setReportQueryHandler(() => {
      throw reportTimeout()
    })

    // when: 조회한다
    const error = await expectApiError(mock.gateway.reports.query(CODE_ONLY), 503)

    // then: 503 report-timeout 오류다
    expect(error.kind).toBe('report-timeout')
  })

  // 테스트 코드: RQ-106
  it('데이터를 초기화하면 처리기와 기록이 지워진다', async () => {
    // given: 처리기를 정하고 한 번 조회했다
    const mock = await mockAs('kim')
    mock.control.setReportQueryHandler(() => CANNED)
    await mock.gateway.reports.query(CODE_ONLY)

    // when: 데이터를 초기화하고 다시 조회한다
    mock.control.resetData()
    const result = await mock.gateway.reports.query(CODE_ONLY)

    // then: 처리기 없이 합성 결과가 오고 기록은 새 요청 하나뿐이다
    expect(result.sql).toContain('fake')
    expect(mock.control.reportQueries()).toEqual([CODE_ONLY])
  })

  // 테스트 코드: RQ-106
  it('정의 위반 오류의 detail은 첫 문구다', () => {
    // when: 위반 둘로 정의 위반 오류를 만든다
    const error = invalidReport([
      { location: ['columns', 1, 'field'], code: 'unknown-field', message: '첫째' },
      { location: ['row_limit'], code: 'row-limit-invalid', message: '둘째' },
    ])

    // then: 422 invalid-report이고 메시지가 첫 문구이며 위반 목록이 둘이다
    expect(error.status).toBe(422)
    expect(error.kind).toBe('invalid-report')
    expect(error.message).toBe('첫째')
    expect(error.problem?.reportErrors).toHaveLength(2)
  })

  // 테스트 코드: RQ-106
  it('열 수만큼 넓은 3행과 서버 시계 날짜로 합성한다', async () => {
    // given: 서버 시계가 2026-12-31 23:30 +09:00다
    const mock = await mockAs('kim')
    mock.clock.setNow('2026-12-31T23:30:00+09:00')

    // when: 조회한다
    const result = await mock.gateway.reports.query(CODE_ONLY)

    // then: 3행에 총 3건, 잘림 없음, 21ms, 서버 날짜, 행 수 제한 100이다
    expect(result.rows).toHaveLength(3)
    expect(result).toMatchObject({ totalCount: 3, truncated: false, elapsedMs: 21, today: '2026-12-31', rowLimit: 100 })
  })

  // 테스트 코드: RQ-106
  it('그룹핑할 때만 합계 행을 준다', async () => {
    // given: Fake 게이트웨이
    const mock = await mockAs('kim')

    // when: Vendor 그룹과 금액 컬럼을 조회한다
    const result = await mock.gateway.reports.query({
      ...CODE_ONLY,
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.amount', group: false },
      ],
    })

    // then: 금액은 합계·정수·단위 krw이고 합계 행은 [null, 6000]이다
    expect(result.columns[1]).toMatchObject({ aggregate: 'sum', valueType: 'integer', format: null, unit: 'krw' })
    expect(result.columns[0]?.unit).toBeNull()
    expect(result.totals).toEqual([null, 6000])
  })

  // 테스트 코드: RQ-106
  it('Action 컬럼과 Deal 숫자의 범위를 서버와 같게 예측한다', async () => {
    // given: Fake 게이트웨이
    const mock = await mockAs('kim')

    // when: Action 유형 그룹과 금액을 조회한다
    const result = await mock.gateway.reports.query({
      ...CODE_ONLY,
      columns: [
        { field: 'action.type', group: true },
        { field: 'deal.amount', group: false },
      ],
    })

    // then: Action 행 범위·JOIN·Deal당 한 번이다
    expect(result).toMatchObject({ rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true })
  })

  // 테스트 코드: RQ-106
  it('모방하는 위반을 서버와 같은 코드·위치·문구로 한꺼번에 알린다', async () => {
    const mock = await mockAs('kim')

    // when: 집계 없는 텍스트 컬럼과 선택지 밖 행 수 제한으로 조회한다
    const error = await expectApiError(
      mock.gateway.reports.query({
        columns: [
          { field: 'deal.vendor', group: true },
          { field: 'deal.code', group: false },
        ],
        conditions: [],
        combine: 'and',
        rowLimit: 7,
      }),
      422,
    )

    // then: 위반 둘이 서버와 같은 위치·code·문구로 모이고 detail은 첫 문구다
    expect(error.kind).toBe('invalid-report')
    expect(error.problem?.reportErrors).toEqual([
      { location: ['columns', 1, 'aggregate'], code: 'aggregate-required', message: '그룹핑할 때 이 컬럼은 집계(건수 또는 고유 건수)를 골라야 합니다. 그룹핑하거나 빼세요' },
      { location: ['row_limit'], code: 'row-limit-invalid', message: '행 수 제한은 100, 1000, 10000 중 하나여야 합니다' },
    ])
    expect(error.message).toBe('그룹핑할 때 이 컬럼은 집계(건수 또는 고유 건수)를 골라야 합니다. 그룹핑하거나 빼세요')
  })

  // 테스트 코드: RQ-106
  it('그룹핑 없는 집계·Action 건수와 컬럼 0개의 위반도 서버처럼 모방한다', async () => {
    const mock = await mockAs('kim')

    // when: 그룹핑 없이 집계·Action 건수를 주고, 컬럼 없는 정의도 조회한다
    const noGroup = await expectApiError(
      mock.gateway.reports.query({
        ...CODE_ONLY,
        columns: [
          { field: 'deal.amount', group: false, aggregate: 'sum' },
          { field: 'action.count', group: false },
        ],
      }),
      422,
    )
    const noColumns = await expectApiError(mock.gateway.reports.query({ ...CODE_ONLY, columns: [] }), 422)

    // then: 서버와 같은 위치·code·문구다
    expect(noGroup.problem?.reportErrors).toEqual([
      { location: ['columns', 0, 'aggregate'], code: 'aggregate-not-allowed', message: '그룹핑이 없으면 집계를 지정할 수 없습니다. 그룹 컬럼을 추가하거나 집계를 빼세요' },
      { location: ['columns', 1], code: 'grouping-required', message: '이 컬럼은 그룹핑할 때만 쓸 수 있습니다. 그룹 컬럼을 추가하세요' },
    ])
    expect(noColumns.problem?.reportErrors).toEqual([
      { location: ['columns'], code: 'columns-count', message: '컬럼은 1개 이상 30개 이하로 지정하세요' },
    ])
  })

  // 테스트 코드: RQ-106
  it('평균·최소·최대 컬럼의 합계도 합성 행에서 계산해 준다', async () => {
    const mock = await mockAs('kim')

    // when: Vendor 그룹과 금액의 합계·평균·최소·최대로 조회한다
    const result = await mock.gateway.reports.query({
      ...CODE_ONLY,
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.amount', group: false, aggregate: 'sum' },
        { field: 'deal.amount', group: false, aggregate: 'avg' },
        { field: 'deal.amount', group: false, aggregate: 'min' },
        { field: 'deal.amount', group: false, aggregate: 'max' },
      ],
    })

    // then: 합계 행은 그룹 칸 null, 합계 6000, 평균 3, 최소 1000, 최대 3000이다
    expect(result.totals).toEqual([null, 6000, 3, 1000, 3000])
  })

  // 테스트 코드: RQ-106
  it('모든 컬럼이 그룹이거나 그룹핑이 없으면 합계가 없다', async () => {
    const mock = await mockAs('kim')

    // when: 모든 컬럼이 그룹인 정의와 그룹핑 없는 정의를 조회한다
    const allGroups = await mock.gateway.reports.query({
      ...CODE_ONLY,
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.status', group: true },
      ],
    })
    const noGroups = await mock.gateway.reports.query(CODE_ONLY)

    // then: 합계 행이 둘 다 null이다
    expect(allGroups.totals).toBeNull()
    expect(noGroups.totals).toBeNull()
  })
})
