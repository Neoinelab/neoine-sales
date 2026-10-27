/**
 * Reports 계약(Reports 2단계 G6~G9). mock과 실제 서버가 같은 모양으로 답해야 한다.
 * 시드에 기대지 않고 카탈로그의 불변식, 모든 역할의 접근, 결과 모양(행 너비·합계), 정의 위반의 code·location만 본다.
 */

import { describe, expect, it } from 'vitest'
import type { ReportQueryInput } from '../../shared/model/reportTypes'
import { expectRejects, type MakeGateway } from './support'

const DEAL_CODE_COLUMN = { field: 'deal.code', format: 'as_is', group: false } as const

const query = (over: Partial<ReportQueryInput> = {}): ReportQueryInput => ({
  columns: [DEAL_CODE_COLUMN],
  conditions: [],
  combine: 'and',
  rowLimit: 100,
  ...over,
})

export function reportsContract(make: MakeGateway): void {
  describe('reports 계약', () => {
    it.each(['admin', 'sales', 'user'] as const)('lets %s read the fields and run a query', async (role) => {
      const { reports } = await make(role)

      const catalog = await reports.fields()
      const result = await reports.query(query())

      expect(catalog.fields.length).toBeGreaterThan(0)
      expect(result.columns).toHaveLength(1)
    })

    it('has 40 fields with defaults inside their own choices', async () => {
      const { reports } = await make('user')

      const catalog = await reports.fields()

      expect(catalog.fields).toHaveLength(40)
      expect(catalog.fields.filter((f) => f.entity === 'deal')).toHaveLength(28)
      expect(catalog.fields.filter((f) => f.entity === 'action')).toHaveLength(12)
      for (const field of catalog.fields) {
        expect(field.formats, field.key).toContain(field.defaultFormat)
        if (field.defaultAggregate !== null && field.aggregates.length > 0) {
          expect(field.aggregates, field.key).toContain(field.defaultAggregate)
        }
      }
    })

    it('exposes the limits, the labels and the shape of every operator', async () => {
      const { reports } = await make('user')

      const catalog = await reports.fields()

      expect(catalog.limits).toMatchObject({ columnsMin: 1, columnsMax: 30, conditionsMax: 20, rowLimits: [100, 1000, 10000], defaultRowLimit: 1000 })
      expect(catalog.entities.map((e) => e.label)).toEqual(['Deal', 'Deal Actions'])
      expect(catalog.operators.find((o) => o.key === 'between')?.shape).toBe('range')
      expect(catalog.relativePeriods.find((p) => p.key === 'last_n_days')?.needsDays).toBe(true)
      for (const field of catalog.fields) {
        for (const operator of field.operators) expect(catalog.operators.map((o) => o.key), field.key).toContain(operator)
      }
    })

    it('answers rows as wide as the columns and no totals without grouping', async () => {
      const { reports } = await make('sales')

      const result = await reports.query(
        query({ columns: [DEAL_CODE_COLUMN, { field: 'deal.name', format: 'as_is', group: false }, { field: 'deal.amount', format: 'krw_thousand', group: false }] }),
      )

      expect(result.columns.map((c) => c.index)).toEqual([0, 1, 2])
      for (const row of result.rows) expect(row).toHaveLength(3)
      expect(result.totals).toBeNull()
      expect(result.rowScope).toBe('deal')
      expect(result.rowLimit).toBe(100)
    })

    it('answers totals as wide as the columns when grouped', async () => {
      const { reports } = await make('sales')

      const result = await reports.query(
        query({
          columns: [
            { field: 'deal.vendor', format: 'name', group: true },
            { field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum' },
          ],
        }),
      )

      expect(result.totals).toHaveLength(2)
      for (const row of result.rows) expect(row).toHaveLength(2)
      expect(result.columns.map((c) => c.group)).toEqual([true, false])
      expect(result.columns[1]?.aggregate).toBe('sum')
    })

    it('uses Action rows when an Action column is chosen', async () => {
      const { reports } = await make('sales')

      const result = await reports.query(query({ columns: [DEAL_CODE_COLUMN, { field: 'action.action', format: 'as_is', group: false }] }))

      expect(result).toMatchObject({ rowScope: 'action', actionFilter: 'join' })
    })

    it('filters Deals by Action existence when only a condition uses an Action field', async () => {
      const { reports } = await make('sales')

      const result = await reports.query(
        query({ conditions: [{ field: 'action.action', operator: 'contains', value: '미팅' }] }),
      )

      expect(result).toMatchObject({ rowScope: 'deal', actionFilter: 'exists' })
    })

    it('rejects an unknown field with its location', async () => {
      const { reports } = await make('user')

      const error = await expectRejects(reports.query(query({ columns: [DEAL_CODE_COLUMN, { field: 'deal.nope', format: 'as_is', group: false }] })), 422)

      expect(error.kind).toBe('invalid-report')
      expect(error.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns', 1, 'field'], code: 'unknown-field' })])
    })

    it('rejects a text column without an aggregate once something is grouped', async () => {
      const { reports } = await make('user')

      const error = await expectRejects(
        reports.query(query({ columns: [{ field: 'deal.vendor', format: 'name', group: true }, DEAL_CODE_COLUMN] })),
        422,
      )

      expect(error.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns', 1, 'aggregate'], code: 'aggregate-required' })])
    })

    it('rejects an aggregate when nothing is grouped', async () => {
      const { reports } = await make('user')

      const error = await expectRejects(
        reports.query(query({ columns: [{ field: 'deal.amount', format: 'krw_thousand', group: false, aggregate: 'sum' }] })),
        422,
      )

      expect(error.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns', 0, 'aggregate'], code: 'aggregate-not-allowed' })])
    })

    it('rejects the Action count column unless something is grouped', async () => {
      const { reports } = await make('user')

      const error = await expectRejects(
        reports.query(query({ columns: [{ field: 'action.count', format: 'thousands', group: false }] })),
        422,
      )

      expect(error.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns', 0], code: 'grouping-required' })])
    })

    it('rejects zero columns and a row limit outside the choices', async () => {
      const { reports } = await make('user')

      const noColumns = await expectRejects(reports.query(query({ columns: [] })), 422)
      const badLimit = await expectRejects(reports.query(query({ rowLimit: 7 })), 422)

      expect(noColumns.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['columns'], code: 'columns-count' })])
      expect(badLimit.problem?.reportErrors).toEqual([expect.objectContaining({ location: ['row_limit'], code: 'row-limit-invalid' })])
    })

    it('collects every violation instead of stopping at the first', async () => {
      const { reports } = await make('user')

      const error = await expectRejects(
        reports.query(query({ columns: [{ field: 'deal.nope', format: 'as_is', group: false }, { field: 'deal.nada', format: 'as_is', group: false }] })),
        422,
      )

      expect(error.problem?.reportErrors).toHaveLength(2)
      expect(error.message).toBe(error.problem?.reportErrors?.[0]?.message)
    })

    it('refuses an anonymous visitor', async () => {
      const gateway = await make('user')
      await gateway.auth.logout()

      await expectRejects(gateway.reports.fields(), 401)
      await expectRejects(gateway.reports.query(query()), 401)
    })
  })
}
