import { describe, expect, it } from 'vitest'
import type { ReportQueryInput, ReportResult } from '../../../shared/model/reportTypes'
import { invalidReport, reportTimeout } from '../errors'
import { REPORT_CATALOG } from '../seed/reportCatalog'
import { expectApiError, mockAs } from '../testing'

/** Reports Fake 자체의 규칙(계약 스위트가 다루지 않는 제어 도구와 합성 결과). */

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
  it('serves a copy of the 40 field catalog that callers may change', async () => {
    const { gateway } = await mockAs('kim')

    const first = await gateway.reports.fields()
    first.fields.length = 0
    const second = await gateway.reports.fields()

    expect(second.fields).toHaveLength(40)
    expect(REPORT_CATALOG.fields).toHaveLength(40)
  })

  it('answers the handler result and records every request', async () => {
    const mock = await mockAs('kim')
    mock.control.setReportQueryHandler(() => CANNED)

    const result = await mock.gateway.reports.query(CODE_ONLY)

    expect(result.rows).toEqual([['20261016-0001']])
    expect(mock.control.reportQueries()).toEqual([CODE_ONLY])
  })

  it('rejects with what the handler throws', async () => {
    const mock = await mockAs('kim')
    mock.control.setReportQueryHandler(() => {
      throw reportTimeout()
    })

    const error = await expectApiError(mock.gateway.reports.query(CODE_ONLY), 503)

    expect(error.kind).toBe('report-timeout')
  })

  it('clears the handler and the records when the data is reset', async () => {
    const mock = await mockAs('kim')
    mock.control.setReportQueryHandler(() => CANNED)
    await mock.gateway.reports.query(CODE_ONLY)

    mock.control.resetData()
    const result = await mock.gateway.reports.query(CODE_ONLY)

    expect(result.sql).toContain('fake')
    expect(mock.control.reportQueries()).toEqual([CODE_ONLY])
  })

  it('builds an invalid report error whose detail is the first message', () => {
    const error = invalidReport([
      { location: ['columns', 1, 'field'], code: 'unknown-field', message: '첫째' },
      { location: ['row_limit'], code: 'row-limit-invalid', message: '둘째' },
    ])

    expect(error.status).toBe(422)
    expect(error.kind).toBe('invalid-report')
    expect(error.message).toBe('첫째')
    expect(error.problem?.reportErrors).toHaveLength(2)
  })

  it('synthesizes three rows as wide as the columns with the server clock date', async () => {
    const mock = await mockAs('kim')
    mock.clock.setNow('2026-12-31T23:30:00+09:00')

    const result = await mock.gateway.reports.query(CODE_ONLY)

    expect(result.rows).toHaveLength(3)
    expect(result).toMatchObject({ totalCount: 3, truncated: false, elapsedMs: 21, today: '2026-12-31', rowLimit: 100 })
  })

  it('adds totals of sum columns only when grouped', async () => {
    const mock = await mockAs('kim')

    const result = await mock.gateway.reports.query({
      ...CODE_ONLY,
      columns: [
        { field: 'deal.vendor', group: true },
        { field: 'deal.amount', group: false },
      ],
    })

    expect(result.columns[1]).toMatchObject({ aggregate: 'sum', valueType: 'integer', format: null, unit: 'krw_thousand' })
    expect(result.columns[0]?.unit).toBeNull()
    expect(result.totals).toEqual([null, 6000])
  })

  it('predicts the same scope as the server for Action columns and Deal numbers', async () => {
    const mock = await mockAs('kim')

    const result = await mock.gateway.reports.query({
      ...CODE_ONLY,
      columns: [
        { field: 'action.type', group: true },
        { field: 'deal.amount', group: false },
      ],
    })

    expect(result).toMatchObject({ rowScope: 'action', actionFilter: 'join', dealNumbersOnce: true })
  })
})
