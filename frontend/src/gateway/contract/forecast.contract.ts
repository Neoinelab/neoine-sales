/**
 * Forecast 요약 계약(P6 R1 AC-1~9). mock과 실제 서버가 같은 결과를 내야 한다.
 * 시드에 기대지 않고 구조·불변식(Lost 제외, Total 정의, 합계 = 행 합, 원장 일치)만 본다.
 */

import { describe, expect, it } from 'vitest'
import type { ForecastQuery, ForecastSummary } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, type MakeGateway } from './support'

const QUARTER_MONTH = 'Quarter와 월은 함께 선택할 수 없습니다.'

/** 같은 조건 Deal 목록(원장)을 전부 읽는다(서버 한도 200건씩). */
async function ledger(gateway: Gateway, query: ForecastQuery) {
  const items = []
  for (let offset = 0; ; offset += 200) {
    const { quarter, ...rest } = query
    const page = await gateway.deals.list({ ...rest, ...(quarter ? { quarters: [quarter] } : {}), offset, limit: 200 })
    items.push(...page.items)
    if (items.length >= page.total || page.items.length === 0) break
  }
  return items
}

const openKeys = (summary: ForecastSummary) => summary.columns.filter((c) => c.outcome === 'open').map((c) => c.key)

export function forecastContract(make: MakeGateway): void {
  describe('forecast 계약', () => {
    it.each(['admin', 'sales', 'user'] as const)('lets %s read the summary', async (role) => {
      const gateway = await make(role)

      const summary = await gateway.forecast.summary({ year: 2026 })

      expect(summary.columns.length).toBeGreaterThan(0)
    })

    it('lists the forecast codes without Lost, in code order, open before the closing won column', async () => {
      const { forecast } = await make('user')

      const { columns } = await forecast.summary({ year: 2026 })

      expect(columns.map((c) => c.key)).not.toContain('lost')
      expect(columns.every((c) => c.outcome === 'open' || c.outcome === 'won')).toBe(true)
      const orders = columns.map((c) => c.order)
      expect(orders).toEqual([...orders].sort((a, b) => a - b))
      expect(columns.map((c) => c.key)).toEqual(expect.arrayContaining(['pipeline', 'best', 'most_likely', 'commit', 'won']))
    })

    it('has a cell for every column in every row and the total row', async () => {
      const { forecast } = await make('user')

      const summary = await forecast.summary({ year: 2026 })

      for (const row of [...summary.rows, summary.totalRow]) {
        for (const column of summary.columns) expect(row.cells[column.key]).toBeDefined()
      }
    })

    it('defines Total as the sum of the open cells, without Won or Lost', async () => {
      const { forecast } = await make('user')

      const summary = await forecast.summary({ year: 2026 })

      for (const row of [...summary.rows, summary.totalRow]) {
        const open = openKeys(summary).map((key) => row.cells[key] ?? { count: 0, amount: 0 })
        expect(row.total).toEqual({
          count: open.reduce((sum, cell) => sum + cell.count, 0),
          amount: open.reduce((sum, cell) => sum + cell.amount, 0),
        })
      }
    })

    it('makes the total row equal to the sum of the rows, cell by cell', async () => {
      const { forecast } = await make('user')

      const summary = await forecast.summary({ year: 2026 })

      for (const column of summary.columns) {
        const count = summary.rows.reduce((sum, row) => sum + (row.cells[column.key]?.count ?? 0), 0)
        const amount = summary.rows.reduce((sum, row) => sum + (row.cells[column.key]?.amount ?? 0), 0)
        expect(summary.totalRow.cells[column.key]).toEqual({ count, amount })
      }
    })

    it.each<[string, ForecastQuery]>([
      ['year', { year: 2026 }],
      ['quarter', { year: 2026, quarter: 4 }],
      ['month', { year: 2026, month: 11 }],
      ['next january', { year: 2027, month: 1 }],
    ])('matches the Deal list ledger without Lost for the %s condition (검수 4)', async (_name, query) => {
      const gateway = await make('user')

      const summary = await gateway.forecast.summary(query)
      const deals = (await ledger(gateway, query)).filter((d) => d.forecastKey !== 'lost')

      const open = new Set(openKeys(summary))
      const openDeals = deals.filter((d) => open.has(d.forecastKey))
      expect(summary.totalRow.total).toEqual({
        count: openDeals.length,
        amount: openDeals.reduce((sum, d) => sum + d.revenueAmount, 0),
      })
      const wonDeals = deals.filter((d) => d.forecastKey === 'won')
      expect(summary.totalRow.cells.won).toEqual({
        count: wonDeals.length,
        amount: wonDeals.reduce((sum, d) => sum + d.revenueAmount, 0),
      })
    })

    it('narrows to one owner when ownerId is given', async () => {
      const gateway = await make('user')
      const all = await gateway.forecast.summary({ year: 2026 })
      const first = all.rows[0]
      if (!first) throw new Error('담당자 행이 하나도 없습니다(시드 Deal 필요).')

      const mine = await gateway.forecast.summary({ year: 2026, ownerId: first.ownerId ?? 0 })

      expect(mine.rows.map((r) => r.ownerId)).toEqual([first.ownerId])
    })

    it('answers basis live with the server time as of', async () => {
      const { forecast } = await make('user')

      const summary = await forecast.summary({ year: 2026 })

      expect(summary.basis).toBe('live')
      expect(Number.isNaN(Date.parse(summary.asOf))).toBe(false)
    })

    it('refuses a quarter together with a month with 422', async () => {
      const { forecast } = await make('user')

      await expectRejects(forecast.summary({ year: 2026, quarter: 1, month: 1 }), 422, QUARTER_MONTH)
    })

    it('answers a live summary without a snapshot period', async () => {
      const { forecast } = await make('user')

      const summary = await forecast.summary({ year: 2026 })

      expect(summary.snapshotPeriod).toBeNull()
    })
  })

  describe('forecast 스냅숏 계약 (P6 R2 AC-16·17)', () => {
    const PERIOD = /^\d{4}-(0[1-9]|1[0-2])$/

    it.each(['admin', 'sales', 'user'] as const)('lets %s list the snapshots', async (role) => {
      const gateway = await make(role)

      const list = await gateway.forecast.snapshots()

      expect(Array.isArray(list)).toBe(true)
    })

    it('lists YYYY-MM periods with a creation time, newest period first', async () => {
      const { forecast } = await make('user')

      const list = await forecast.snapshots()

      for (const item of list) {
        expect(item.period).toMatch(PERIOD)
        expect(Number.isNaN(Date.parse(item.takenAt))).toBe(false)
      }
      const periods = list.map((item) => item.period)
      expect(periods).toEqual([...periods].sort().reverse())
    })

    it('answers 404 for a period that was never stored', async () => {
      const { forecast } = await make('user')

      await expectRejects(forecast.snapshotSummary('1999-01', { year: 2026 }), 404)
    })

    it.each(['2026-9', 'abc', '2026-13'])('answers 404 for the malformed period %j', async (period) => {
      const { forecast } = await make('user')

      await expectRejects(forecast.snapshotSummary(period, { year: 2026 }), 404)
    })

    it('judges a quarter together with a month (422) before it looks for the period', async () => {
      const { forecast } = await make('user')

      await expectRejects(forecast.snapshotSummary('1999-01', { year: 2026, quarter: 1, month: 1 }), 422, QUARTER_MONTH)
    })

    it('reads every listed snapshot as a snapshot summary stamped with its creation time', async () => {
      const { forecast } = await make('user')

      for (const item of await forecast.snapshots()) {
        const summary = await forecast.snapshotSummary(item.period, { year: Number(item.period.slice(0, 4)) })

        expect(summary.basis).toBe('snapshot')
        expect(summary.snapshotPeriod).toBe(item.period)
        expect(summary.asOf).toBe(item.takenAt)
        expect(summary.columns.map((c) => c.key)).not.toContain('lost')
      }
    })
  })
}
