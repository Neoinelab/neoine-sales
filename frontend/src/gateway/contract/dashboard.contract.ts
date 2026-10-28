/**
 * Dashboard 요약 계약(Dashboard AC-1~8·18). mock과 실제 서버가 같은 결과를 내야 한다.
 * 시드에 기대지 않고 구조·불변식(Lost 제외, 합계 = 항목 합, 분기 4개, 주의 타일이 기간을 무시, Forecast 요약·Deal 목록
 * 원장과 일치)만 본다.
 */

import { describe, expect, it } from 'vitest'
import type { DashboardQuery, DealListQuery, ForecastCell } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, type MakeGateway } from './support'

const STATUS_KEYS = ['prospecting', 'introduction', 'poc_preparation', 'poc_completed', 'technical_evaluation', 'price_negotiation', 'contract_completed']

/** 같은 조건 Deal 목록(원장)의 (건수, 금액 합). 서버 한도 200건씩 모두 읽는다. */
async function ledger(gateway: Gateway, query: DealListQuery): Promise<ForecastCell> {
  const items = []
  for (let offset = 0; ; offset += 200) {
    const page = await gateway.deals.list({ ...query, offset, limit: 200 })
    items.push(...page.items)
    if (items.length >= page.total || page.items.length === 0) break
  }
  return { count: items.length, amount: items.reduce((sum, d) => sum + d.revenueAmount, 0) }
}

const sum = (cells: ForecastCell[]): ForecastCell =>
  cells.reduce((total, c) => ({ count: total.count + c.count, amount: total.amount + c.amount }), { count: 0, amount: 0 })

/** 응답 forecast.columns에서 만든 Drill-down Forecast key 집합(Lost 제외 = open + won, Open = open). */
function keySets(columns: { key: string; outcome: string }[]): { open: string[]; notLost: string[] } {
  return {
    open: columns.filter((c) => c.outcome === 'open').map((c) => c.key),
    notLost: columns.filter((c) => c.outcome !== 'lost').map((c) => c.key),
  }
}

const cellOf = ({ count, amount }: ForecastCell): ForecastCell => ({ count, amount })

export function dashboardContract(make: MakeGateway): void {
  describe('dashboard 계약', () => {
    it.each(['admin', 'sales', 'user'] as const)('lets %s read the summary', async (role) => {
      const gateway = await make(role)

      const summary = await gateway.dashboard.summary({ year: 2026 })

      expect(summary.statuses.items.length).toBeGreaterThan(0)
    })

    it.each([1899, 10_000])('refuses the year %i with 422', async (year) => {
      const { dashboard } = await make('user')

      await expectRejects(dashboard.summary({ year }), 422)
    })

    it('refuses a quarter outside 1 to 4 with 422', async () => {
      const { dashboard } = await make('user')

      await expectRejects(dashboard.summary({ year: 2026, quarters: [5] as never }), 422)
    })

    it('answers the server time as asOf and the business date as today', async () => {
      const { dashboard } = await make('user')

      const summary = await dashboard.summary({ year: 2026 })

      expect(Number.isNaN(Date.parse(summary.asOf))).toBe(false)
      expect(summary.today).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })

    it('echoes the period with its date range', async () => {
      const { dashboard } = await make('user')

      expect((await dashboard.summary({ year: 2026 })).period).toEqual({ year: 2026, quarter: null, quarters: [], from: '2026-01-01', to: '2026-12-31' })
      expect((await dashboard.summary({ year: 2026, quarters: [3] })).period).toEqual({ year: 2026, quarter: 3, quarters: [3], from: '2026-07-01', to: '2026-09-30' })
    })

    it('lists the forecast codes without Lost, in code order, with a cell for every column', async () => {
      const { dashboard } = await make('user')

      const { forecast } = await dashboard.summary({ year: 2026 })

      expect(forecast.columns.map((c) => c.key)).not.toContain('lost')
      const orders = forecast.columns.map((c) => c.order)
      expect(orders).toEqual([...orders].sort((a, b) => a - b))
      expect(Object.keys(forecast.cells).sort()).toEqual(forecast.columns.map((c) => c.key).sort())
    })

    it.each<[string, DashboardQuery, { year: number; quarter?: 1 | 2 | 3 | 4 }]>([
      ['year', { year: 2026 }, { year: 2026 }],
      ['quarter', { year: 2026, quarters: [4] }, { year: 2026, quarter: 4 }],
    ])('makes the forecast tiles equal the forecast summary total for the %s condition (AC-3)', async (_name, query, forecastQuery) => {
      const gateway = await make('user')

      const dashboard = await gateway.dashboard.summary(query)
      const summary = await gateway.forecast.summary(forecastQuery)

      expect(dashboard.forecast.columns.map((c) => c.key)).toEqual(summary.columns.map((c) => c.key))
      for (const column of summary.columns) expect(cellOf(dashboard.forecast.cells[column.key] ?? { count: -1, amount: -1 })).toEqual(summary.totalRow.cells[column.key])
      expect(dashboard.forecast.openTotal).toEqual(summary.totalRow.total)
    })

    it('lists every status code in order and makes the status total the sum of the items (AC-4)', async () => {
      const { dashboard } = await make('user')

      const { statuses } = await dashboard.summary({ year: 2026 })

      expect(statuses.items.map((i) => i.key)).toEqual(expect.arrayContaining(STATUS_KEYS))
      const orders = statuses.items.map((i) => i.order)
      expect(orders).toEqual([...orders].sort((a, b) => a - b))
      expect(statuses.total).toEqual(sum(statuses.items))
    })

    it('counts Won but not Lost in the status items: total = open total + won cell', async () => {
      const { dashboard } = await make('user')

      const { statuses, forecast } = await dashboard.summary({ year: 2026 })

      expect(statuses.total).toEqual(sum([forecast.openTotal, forecast.cells.won ?? { count: 0, amount: 0 }]))
    })

    it.each<[string, DashboardQuery]>([
      ['year', { year: 2026 }],
      ['quarter', { year: 2026, quarters: [4] }],
      ['several quarters', { year: 2026, quarters: [1, 3] }],
    ])('matches the Deal list ledger of the status drill-down for the %s condition (AC-18)', async (_name, query) => {
      const gateway = await make('user')

      const { statuses } = await gateway.dashboard.summary(query)

      for (const item of statuses.items) {
        const found = await ledger(gateway, { ...query, statusKey: item.key, forecastOutcome: 'not_lost' })
        expect(found, item.key).toEqual(cellOf(item))
      }
      expect(await ledger(gateway, { ...query, forecastOutcome: 'not_lost' })).toEqual(statuses.total)
    })

    it('matches the Deal list ledger of the Open total (AC-18)', async () => {
      const gateway = await make('user')

      const { forecast } = await gateway.dashboard.summary({ year: 2026, quarters: [4] })

      expect(await ledger(gateway, { year: 2026, quarters: [4], forecastOutcome: 'open' })).toEqual(forecast.openTotal)
    })

    it('always answers Q1 to Q4 whatever quarter is chosen (AC-5)', async () => {
      const { dashboard } = await make('user')

      const whole = await dashboard.summary({ year: 2026 })
      const second = await dashboard.summary({ year: 2026, quarters: [2] })

      expect(whole.quarters.map((q) => q.quarter)).toEqual([1, 2, 3, 4])
      expect(second.quarters).toEqual(whole.quarters)
    })

    it('makes each quarter equal the forecast summary of that quarter (AC-5)', async () => {
      const gateway = await make('user')

      const { quarters } = await gateway.dashboard.summary({ year: 2026, quarters: [2] })

      for (const row of quarters) {
        const summary = await gateway.forecast.summary({ year: 2026, quarter: row.quarter })
        for (const column of summary.columns) expect(row.cells[column.key], `Q${row.quarter} ${column.key}`).toEqual(summary.totalRow.cells[column.key])
        expect(row.openTotal).toEqual(summary.totalRow.total)
        const won = summary.totalRow.cells.won ?? { count: 0, amount: 0 }
        expect(row.total).toEqual(sum([summary.totalRow.total, won]))
      }
    })

    it('matches the Deal list ledger of every quarter total (AC-18)', async () => {
      const gateway = await make('user')

      const { quarters } = await gateway.dashboard.summary({ year: 2026 })

      for (const row of quarters) {
        expect(await ledger(gateway, { year: 2026, quarters: [row.quarter], forecastOutcome: 'not_lost' }), `Q${row.quarter}`).toEqual(row.total)
      }
    })

    it('ignores the period for the attention counts (AC-6)', async () => {
      const { dashboard } = await make('user')

      const thisYear = await dashboard.summary({ year: 2026 })
      const quarter = await dashboard.summary({ year: 2026, quarters: [1] })
      const ancient = await dashboard.summary({ year: 1999 })

      expect(quarter.attention).toEqual(thisYear.attention)
      expect(ancient.attention).toEqual(thisYear.attention)
    })

    it('makes the attention counts equal the Deal list overdue and stale totals (AC-6·18)', async () => {
      const gateway = await make('user')

      const { attention } = await gateway.dashboard.summary({ year: 2026 })

      expect(attention.overdue).toBe((await ledger(gateway, { overdue: true })).count)
      expect(attention.stale).toBe((await ledger(gateway, { stale: true })).count)
    })

    it('counts the open deals of the business-date month and quarter (AC-6·7)', async () => {
      const gateway = await make('user')

      const { attention, today } = await gateway.dashboard.summary({ year: 2020 })

      const year = Number(today.slice(0, 4))
      const month = Number(today.slice(5, 7))
      expect(attention.closingThisMonth).toMatchObject({ year, month })
      expect(attention.closingThisQuarter).toMatchObject({ year, quarter: Math.ceil(month / 3) })
      expect(attention.closingThisMonth.count).toBe((await ledger(gateway, { year, month, forecastOutcome: 'open' })).count)
      expect(attention.closingThisQuarter.count).toBe(
        (await ledger(gateway, { year, quarters: [attention.closingThisQuarter.quarter as 1 | 2 | 3 | 4], forecastOutcome: 'open' })).count,
      )
    })

    it('reports the stale days of the alert settings', async () => {
      const gateway = await make('user')

      const { attention } = await gateway.dashboard.summary({ year: 2026 })

      expect(attention.staleDays).toBe((await gateway.alerts.get()).staleDays)
    })

    it('narrows everything to one owner and keeps the attention counts on the same owner (AC-6)', async () => {
      const gateway = await make('user')
      const all = await gateway.dashboard.summary({ year: 2026 })
      const owners = (await gateway.deals.list({ year: 2026, limit: 200 })).items.map((d) => d.ownerId)
      const ownerId = owners[0]
      if (ownerId === undefined) throw new Error('2026년 Deal이 하나도 없습니다(시드 Deal 필요).')

      const mine = await gateway.dashboard.summary({ year: 2026, ownerId })

      expect(mine.statuses.total).toEqual(await ledger(gateway, { year: 2026, ownerId, forecastOutcome: 'not_lost' }))
      expect(mine.attention.overdue).toBe((await ledger(gateway, { ownerId, overdue: true })).count)
      expect(mine.attention.stale).toBe((await ledger(gateway, { ownerId, stale: true })).count)
      expect(mine.statuses.total.count).toBeLessThanOrEqual(all.statuses.total.count)
    })

    it('matches the Deal list ledger of the Forecast key sets that Drill-down sends (다중 조건 AC-16)', async () => {
      const gateway = await make('user')
      const query: DashboardQuery = { year: 2026, quarters: [4] }

      const { statuses, forecast, quarters } = await gateway.dashboard.summary(query)
      const sets = keySets(forecast.columns)

      expect(sets.open.length).toBeGreaterThan(0)
      for (const item of statuses.items) {
        const found = await ledger(gateway, { ...query, statusKey: item.key, forecastKeys: sets.notLost })
        expect(found, item.key).toEqual(cellOf(item))
      }
      expect(await ledger(gateway, { ...query, forecastKeys: sets.notLost })).toEqual(statuses.total)
      expect(await ledger(gateway, { ...query, forecastKeys: sets.open })).toEqual(forecast.openTotal)
      for (const row of quarters) {
        const scope = { year: 2026, quarters: [row.quarter] } as const
        expect(await ledger(gateway, { ...scope, forecastKeys: sets.notLost }), `Q${row.quarter} total`).toEqual(row.total)
        expect(await ledger(gateway, { ...scope, forecastKeys: sets.open }), `Q${row.quarter} open`).toEqual(row.openTotal)
      }
    })

    it('matches the Forecast key set ledger of the closing counts (다중 조건 AC-16)', async () => {
      const gateway = await make('user')

      const { attention, today, forecast } = await gateway.dashboard.summary({ year: 2020 })
      const { open } = keySets(forecast.columns)

      const year = Number(today.slice(0, 4))
      const month = Number(today.slice(5, 7))
      expect(attention.closingThisMonth.count).toBe((await ledger(gateway, { year, month, forecastKeys: open })).count)
      expect(attention.closingThisQuarter.count).toBe(
        (await ledger(gateway, { year, quarters: [attention.closingThisQuarter.quarter as 1 | 2 | 3 | 4], forecastKeys: open })).count,
      )
    })

    it('includes an open Forecast code added by the admin in both key sets and the ledger (다중 조건 AC-14·16)', async () => {
      const admin = await make('admin')
      const added = await admin.codes.create({ kind: 'forecast', name: 'Verbal' })

      const { forecast } = await admin.dashboard.summary({ year: 2026 })
      const sets = keySets(forecast.columns)

      expect(sets.open).toContain(added.key)
      expect(sets.notLost).toContain(added.key)
      expect(await ledger(admin, { year: 2026, forecastKeys: sets.open })).toEqual(forecast.openTotal)
    })

    describe('Quarter 다중 선택 (AC-06·07·08·21)', () => {
      it('makes the forecast tiles the sum of the chosen quarter rows (AC-06)', async () => {
        const { dashboard } = await make('user')

        const chosen = await dashboard.summary({ year: 2026, quarters: [1, 3] })

        const rows = chosen.quarters.filter((q) => q.quarter === 1 || q.quarter === 3)
        for (const column of chosen.forecast.columns) {
          expect(chosen.forecast.cells[column.key], column.key).toEqual(sum(rows.map((r) => r.cells[column.key] ?? { count: 0, amount: 0 })))
        }
        expect(chosen.forecast.openTotal).toEqual(sum(rows.map((r) => r.openTotal)))
      })

      it('makes the status total the sum of the chosen quarter totals (Lost excluded) (AC-06)', async () => {
        const { dashboard } = await make('user')

        const chosen = await dashboard.summary({ year: 2026, quarters: [1, 3] })

        expect(chosen.statuses.total).toEqual(sum(chosen.quarters.filter((q) => q.quarter === 1 || q.quarter === 3).map((q) => q.total)))
      })

      it('keeps the four quarter rows and the attention counts whatever quarters are chosen (AC-07)', async () => {
        const { dashboard } = await make('user')

        const whole = await dashboard.summary({ year: 2026 })
        const chosen = await dashboard.summary({ year: 2026, quarters: [1, 3] })

        expect(chosen.quarters).toEqual(whole.quarters)
        expect(chosen.attention).toEqual(whole.attention)
      })

      it('describes several chosen quarters in the period (AC-08)', async () => {
        const { dashboard } = await make('user')

        expect((await dashboard.summary({ year: 2026, quarters: [3, 1] })).period).toEqual({ year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' })
      })

      it('reads all four quarters like no quarter (AC-02·08)', async () => {
        const { dashboard } = await make('user')

        const four = await dashboard.summary({ year: 2026, quarters: [1, 2, 3, 4] })
        const none = await dashboard.summary({ year: 2026 })

        expect(four.period).toEqual(none.period)
        expect(four.period.quarters).toEqual([])
        expect(four.statuses).toEqual(none.statuses)
        expect(four.forecast).toEqual(none.forecast)
      })

      it('matches the Deal list ledger of the same several quarters (AC-21)', async () => {
        const gateway = await make('user')
        const query = { year: 2026, quarters: [1, 3] } as const

        const { statuses, forecast } = await gateway.dashboard.summary(query)
        const sets = keySets(forecast.columns)

        expect(await ledger(gateway, { ...query, forecastKeys: sets.notLost })).toEqual(statuses.total)
        expect(await ledger(gateway, { ...query, forecastKeys: sets.open })).toEqual(forecast.openTotal)
        for (const item of statuses.items) expect(await ledger(gateway, { ...query, statusKey: item.key, forecastKeys: sets.notLost }), item.key).toEqual(cellOf(item))
      })

      it.each([[[0]], [[1, 7]], [[1, 2, 3, 4, 1]]])('refuses the quarters %j with 422', async (quarters) => {
        const { dashboard } = await make('user')

        await expectRejects(dashboard.summary({ year: 2026, quarters: quarters as never }), 422)
      })
    })
  })
}
