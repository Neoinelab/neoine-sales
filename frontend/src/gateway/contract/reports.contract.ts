/**
 * Reports 계약. mock과 실제 서버가 같은 모양으로 답해야 한다.
 * 시드에 기대지 않고 카탈로그의 불변식, 모든 역할의 접근, 결과 모양(행 너비·합계), 정의 위반의 code·location만 본다.
 */

import { describe, expect, it } from 'vitest'
import type { ReportQueryInput } from '../../shared/model/reportTypes'
import { expectRejects, type MakeGateway } from './support'

const DEAL_CODE_COLUMN = { field: 'deal.code', group: false } as const

const query = (over: Partial<ReportQueryInput> = {}): ReportQueryInput => ({
  columns: [DEAL_CODE_COLUMN],
  conditions: [],
  combine: 'and',
  rowLimit: 100,
  ...over,
})

export function reportsContract(make: MakeGateway): void {
  describe('reports 계약', () => {
    // 테스트 코드: RQ-107
    it.each(['admin', 'sales', 'user'] as const)('%s 역할이 필드 목록을 읽고 조회를 실행한다', async (role) => {
      // given: 그 역할로 로그인한 게이트웨이
      const { reports } = await make(role)

      // when: 필드 목록을 읽고 조회를 실행한다
      const catalog = await reports.fields()
      const result = await reports.query(query())

      // then: 필드가 있고 결과 열이 하나다
      expect(catalog.fields.length).toBeGreaterThan(0)
      expect(result.columns).toHaveLength(1)
    })

    it('세 엔티티의 필드를 가지며 기본값은 자기 선택지 안에 있다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 필드 목록을 읽는다
      const catalog = await reports.fields()

      expect(catalog.fields).toHaveLength(45)
      expect(catalog.fields.filter((f) => f.entity === 'deal')).toHaveLength(29)
      expect(catalog.fields.filter((f) => f.entity === 'action')).toHaveLength(12)
      expect(catalog.fields.filter((f) => f.entity === 'comment')).toHaveLength(4)
      for (const field of catalog.fields) {
        if (['text', 'code', 'user', 'number'].includes(field.type)) {
          expect(field.formats, field.key).toEqual([])
          expect(field.defaultFormat, field.key).toBeNull()
        } else {
          expect(field.formats, field.key).toContain(field.defaultFormat)
        }
        expect(field.unit, field.key).toBe(field.key === 'deal.amount' ? 'krw' : null)
        if (field.defaultAggregate !== null && field.aggregates.length > 0) {
          expect(field.aggregates, field.key).toContain(field.defaultAggregate)
        }
      }
    })

    it('날짜 포맷 7개를 나열하고 묶음 포맷만 쿼리를 바꾼다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 필드 목록을 읽는다
      const catalog = await reports.fields()

      // then: 포맷 7개이고 예전 포맷은 없으며 쿼리를 바꾸는 것은 ymd·year·quarter·month다
      expect(catalog.formats.map((f) => f.key)).toEqual(['ymd', 'ymd_hm', 'year', 'quarter', 'month', 'weekday', 'relative'])
      for (const legacy of ['as_is', 'prefix', 'name', 'key', 'thousands', 'krw_thousand', 'krw_million', 'decimal1', 'percent_share']) expect(catalog.formats.map((f) => f.key)).not.toContain(legacy)
      expect(catalog.formats.filter((f) => f.affectsQuery).map((f) => f.key)).toEqual(['ymd', 'year', 'quarter', 'month'])
    })

    // 최종 업데이트·Status 진입일·수행일·종료일은 날짜 필드이고 시:분 포맷이 없다.
    it('lists the last update, status entry, performed and closed fields as dates without the time format', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 필드 목록을 읽는다
      const catalog = await reports.fields()

      // then: 네 필드는 date 형식이고 기본 포맷이 ymd이며 ymd_hm을 고를 수 없다(등록일은 그대로 datetime이다)
      for (const key of ['deal.last_updated_at', 'deal.status_changed_at', 'action.acted_at', 'action.closed_at']) {
        const field = catalog.fields.find((f) => f.key === key)
        expect(field?.type, key).toBe('date')
        expect(field?.defaultFormat, key).toBe('ymd')
        expect(field?.formats, key).not.toContain('ymd_hm')
      }
      expect(catalog.fields.find((f) => f.key === 'deal.created_at')).toMatchObject({ type: 'datetime', defaultFormat: 'ymd_hm' })
    })

    it('포맷 없는 필드의 열은 포맷 null로 답하고 앞 N자를 유지한다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 앞 N자 4인 Deal 이름 컬럼을 조회한다
      const result = await reports.query(query({ columns: [{ field: 'deal.name', prefixLength: 4, group: false }] }))

      // then: 포맷 null, 앞 N자 4다
      expect(result.columns[0]).toMatchObject({ field: 'deal.name', format: null, prefixLength: 4 })
    })

    it('한도와 라벨, 모든 연산자의 모양을 알린다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 필드 목록을 읽는다
      const catalog = await reports.fields()

      // then: 한도·엔터티 이름·연산자 모양·상대 기간이 맞고 필드의 모든 연산자가 어휘에 있다
      expect(catalog.limits).toMatchObject({ columnsMin: 1, columnsMax: 30, conditionsMax: 20, rowLimits: [100, 1000, 10000], defaultRowLimit: 1000 })
      expect(catalog.entities.map((e) => e.label)).toEqual(['Deal', 'Deal Actions', 'Comments'])
      expect(catalog.operators.find((o) => o.key === 'between')?.shape).toBe('range')
      expect(catalog.relativePeriods.find((p) => p.key === 'last_n_days')?.needsDays).toBe(true)
      for (const field of catalog.fields) {
        for (const operator of field.operators) expect(catalog.operators.map((o) => o.key), field.key).toContain(operator)
      }
    })

    // 테스트 코드: RQ-106
    it('그룹핑이 없으면 열 수만큼 넓은 행을 주고 합계 행은 없다', async () => {
      // given: sales 게이트웨이
      const { reports } = await make('sales')

      // when: 컬럼 셋을 그룹핑 없이 조회한다
      const result = await reports.query(
        query({ columns: [DEAL_CODE_COLUMN, { field: 'deal.name', group: false }, { field: 'deal.amount', group: false }] }),
      )

      // then: 열 index 0~2, 행 너비 3, 합계 행 null, Deal 행 범위, 행 수 100이다
      expect(result.columns.map((c) => c.index)).toEqual([0, 1, 2])
      for (const row of result.rows) expect(row).toHaveLength(3)
      expect(result.totals).toBeNull()
      expect(result.rowScope).toBe('deal')
      expect(result.rowLimit).toBe(100)
    })

    // 테스트 코드: RQ-106
    it('그룹핑하면 열 수만큼 넓은 합계 행을 준다', async () => {
      // given: sales 게이트웨이
      const { reports } = await make('sales')

      // when: Vendor 그룹과 금액 합계를 조회한다
      const result = await reports.query(
        query({
          columns: [
            { field: 'deal.vendor', group: true },
            { field: 'deal.amount', group: false, aggregate: 'sum' },
          ],
        }),
      )

      // then: 합계 행·행 너비 2, 그룹 표시, 집계, 포맷·단위가 맞다
      expect(result.totals).toHaveLength(2)
      for (const row of result.rows) expect(row).toHaveLength(2)
      expect(result.columns.map((c) => c.group)).toEqual([true, false])
      expect(result.columns[1]?.aggregate).toBe('sum')
      expect(result.columns.map((c) => [c.format, c.unit])).toEqual([[null, null], [null, 'krw']])
    })

    // 테스트 코드: RQ-106
    it('Action 컬럼을 고르면 Action 행 범위다', async () => {
      // given: sales 게이트웨이
      const { reports } = await make('sales')

      // when: Action 컬럼을 조회한다
      const result = await reports.query(query({ columns: [DEAL_CODE_COLUMN, { field: 'action.action', group: false }] }))

      // then: Action 행 범위에 JOIN이다
      expect(result).toMatchObject({ rowScope: 'action', actionFilter: 'join' })
    })

    // 테스트 코드: RQ-106
    it('Action 필드가 조건에만 있으면 Action 존재로 Deal을 거른다', async () => {
      // given: sales 게이트웨이
      const { reports } = await make('sales')

      // when: Action 조건만 있는 정의를 조회한다
      const result = await reports.query(
        query({ conditions: [{ field: 'action.action', operator: 'contains', value: '미팅' }] }),
      )

      // then: Deal 행 범위에 EXISTS다
      expect(result).toMatchObject({ rowScope: 'deal', actionFilter: 'exists' })
    })

    // 테스트 코드: RQ-106
    it('모르는 필드는 위치와 함께 거절한다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 모르는 필드를 조회한다
      const error = await expectRejects(reports.query(query({ columns: [DEAL_CODE_COLUMN, { field: 'deal.nope', group: false }] })), 422)

      // then: 422 invalid-report에 컬럼 1 field의 unknown-field 하나다
      expect(error.kind).toBe('invalid-report')
      expect(error.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns', 1, 'field'], code: 'unknown-field' })])
    })

    // 테스트 코드: RQ-106
    it('그룹핑이 있으면 집계 없는 텍스트 컬럼을 거절한다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: Vendor 그룹과 집계 없는 Deal code를 조회한다
      const error = await expectRejects(
        reports.query(query({ columns: [{ field: 'deal.vendor', group: true }, DEAL_CODE_COLUMN] })),
        422,
      )

      // then: 컬럼 1 aggregate의 aggregate-required다
      expect(error.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns', 1, 'aggregate'], code: 'aggregate-required' })])
    })

    // 테스트 코드: RQ-106
    it('그룹핑이 없는데 집계를 주면 거절한다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 그룹 없이 금액 합계를 조회한다
      const error = await expectRejects(
        reports.query(query({ columns: [{ field: 'deal.amount', group: false, aggregate: 'sum' }] })),
        422,
      )

      // then: 컬럼 0 aggregate의 aggregate-not-allowed다
      expect(error.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns', 0, 'aggregate'], code: 'aggregate-not-allowed' })])
    })

    // 테스트 코드: RQ-106
    it('그룹핑이 없으면 Action 건수 컬럼을 거절한다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 그룹 없이 Action 건수를 조회한다
      const error = await expectRejects(
        reports.query(query({ columns: [{ field: 'action.count', group: false }] })),
        422,
      )

      // then: 컬럼 0의 grouping-required다
      expect(error.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns', 0], code: 'grouping-required' })])
    })

    // 테스트 코드: RQ-106
    it('컬럼 0개와 선택지 밖 행 수 제한을 거절한다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 컬럼 없는 정의와 행 수 7인 정의를 조회한다
      const noColumns = await expectRejects(reports.query(query({ columns: [] })), 422)
      const badLimit = await expectRejects(reports.query(query({ rowLimit: 7 })), 422)

      // then: columns-count와 row-limit-invalid다
      expect(noColumns.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns'], code: 'columns-count' })])
      expect(badLimit.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['row_limit'], code: 'row-limit-invalid' })])
    })

    // 테스트 코드: RQ-106
    it('처음 위반에서 멈추지 않고 모든 위반을 모은다', async () => {
      // given: user 게이트웨이
      const { reports } = await make('user')

      // when: 모르는 필드 둘을 조회한다
      const error = await expectRejects(
        reports.query(query({ columns: [{ field: 'deal.nope', group: false }, { field: 'deal.nada', group: false }] })),
        422,
      )

      // then: 위반 둘이고 메시지는 첫 위반 문구다
      expect(error.problem?.reportErrors).toHaveLength(2)
      expect(error.message).toBe(error.problem?.reportErrors?.[0]?.message)
    })

    // 테스트 코드: RQ-107
    it('로그인하지 않은 방문자는 거절한다', async () => {
      // given: 로그아웃한 게이트웨이
      const gateway = await make('user')
      await gateway.auth.logout()

      // when·then: 카탈로그와 조회 모두 401로 거절된다
      await expectRejects(gateway.reports.fields(), 401)
      await expectRejects(gateway.reports.query(query()), 401)
    })
  })
}
