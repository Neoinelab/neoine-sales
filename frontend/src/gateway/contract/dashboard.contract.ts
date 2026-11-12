/**
 * Dashboard 요약 계약. Fake와 실제 서버가 같은 결과를 내야 한다.
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
    it.each(['admin', 'sales', 'user'] as const)('%s 역할이 요약을 읽는다', async (role) => {
      // given: 해당 역할의 게이트웨이
      const gateway = await make(role)

      // when: 2026년 요약을 조회한다
      const summary = await gateway.dashboard.summary({ year: 2026 })

      // then: Status 항목이 있다
      expect(summary.statuses.items.length).toBeGreaterThan(0)
    })

    it.each([1899, 10_000])('연도 %i은 422로 거절한다', async (year) => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when·then: 범위 밖 연도로 조회하면 422다
      await expectRejects(dashboard.summary({ year }), 422)
    })

    it('1~4 밖의 분기는 422로 거절한다', async () => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when·then: 분기 5로 조회하면 422다
      await expectRejects(dashboard.summary({ year: 2026, quarters: [5] as never }), 422)
    })

    it('서버 시각을 asOf로, 업무 날짜를 today로 답한다', async () => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when: 요약을 조회한다
      const summary = await dashboard.summary({ year: 2026 })

      // then: asOf는 시각이고 today는 날짜 형식이다
      expect(Number.isNaN(Date.parse(summary.asOf))).toBe(false)
      expect(summary.today).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })

    it('기간을 날짜 범위와 함께 돌려준다', async () => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when: 연도만, Q3로 각각 조회한다
      const whole = (await dashboard.summary({ year: 2026 })).period
      const third = (await dashboard.summary({ year: 2026, quarters: [3] })).period

      // then: 연 전체와 Q3 범위다
      expect(whole).toEqual({ year: 2026, quarter: null, quarters: [], from: '2026-01-01', to: '2026-12-31' })
      expect(third).toEqual({ year: 2026, quarter: 3, quarters: [3], from: '2026-07-01', to: '2026-09-30' })
    })

    it('Forecast 코드를 Lost 없이 코드 순서로 나열하고 열마다 셀이 있다', async () => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when: 요약을 조회한다
      const { forecast } = await dashboard.summary({ year: 2026 })

      // then: Lost 열이 없고 order가 오름차순이며 셀 key가 열 key와 같다
      expect(forecast.columns.map((c) => c.key)).not.toContain('lost')
      const orders = forecast.columns.map((c) => c.order)
      expect(orders).toEqual([...orders].sort((a, b) => a - b))
      expect(Object.keys(forecast.cells).sort()).toEqual(forecast.columns.map((c) => c.key).sort())
    })

    it.each<[string, DashboardQuery, { year: number; quarter?: 1 | 2 | 3 | 4 }]>([
      ['연도', { year: 2026 }, { year: 2026 }],
      ['분기', { year: 2026, quarters: [4] }, { year: 2026, quarter: 4 }],
    ])('Forecast 타일이 %s 조건의 Forecast 요약 합계 행과 같다', async (_name, query, forecastQuery) => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: Dashboard 요약과 같은 조건의 Forecast 요약을 조회한다
      const dashboard = await gateway.dashboard.summary(query)
      const summary = await gateway.forecast.summary(forecastQuery)

      // then: 열·셀·Open 합계가 같다
      expect(dashboard.forecast.columns.map((c) => c.key)).toEqual(summary.columns.map((c) => c.key))
      for (const column of summary.columns) expect(cellOf(dashboard.forecast.cells[column.key] ?? { count: -1, amount: -1 })).toEqual(summary.totalRow.cells[column.key])
      expect(dashboard.forecast.openTotal).toEqual(summary.totalRow.total)
    })

    it('모든 Status 코드를 순서대로 나열하고 합계는 항목의 합이다', async () => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when: 요약을 조회한다
      const { statuses } = await dashboard.summary({ year: 2026 })

      // then: 코드가 모두 있고 순서대로이며 합계가 항목 합이다
      expect(statuses.items.map((i) => i.key)).toEqual(expect.arrayContaining(STATUS_KEYS))
      const orders = statuses.items.map((i) => i.order)
      expect(orders).toEqual([...orders].sort((a, b) => a - b))
      expect(statuses.total).toEqual(sum(statuses.items))
    })

    it('Status 항목은 Won은 세고 Lost는 세지 않는다: 합계 = Open 합계 + Won 셀', async () => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when: 요약을 조회한다
      const { statuses, forecast } = await dashboard.summary({ year: 2026 })

      // then: Status 합계가 Open 합계 + Won 셀이다
      expect(statuses.total).toEqual(sum([forecast.openTotal, forecast.cells.won ?? { count: 0, amount: 0 }]))
    })

    it.each<[string, DashboardQuery]>([
      ['연도', { year: 2026 }],
      ['분기', { year: 2026, quarters: [4] }],
      ['여러 분기', { year: 2026, quarters: [1, 3] }],
    ])('Status Drill-down 목록 원장이 %s 조건의 숫자와 같다', async (_name, query) => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: 요약을 조회한다
      const { statuses } = await gateway.dashboard.summary(query)

      // then: Status 항목과 합계가 Lost 제외 목록 원장과 같다
      for (const item of statuses.items) {
        const found = await ledger(gateway, { ...query, statusKey: item.key, forecastOutcome: 'not_lost' })
        expect(found, item.key).toEqual(cellOf(item))
      }
      expect(await ledger(gateway, { ...query, forecastOutcome: 'not_lost' })).toEqual(statuses.total)
    })

    it('Open 합계가 목록 원장과 같다', async () => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: Q4 요약을 조회한다
      const { forecast } = await gateway.dashboard.summary({ year: 2026, quarters: [4] })

      // then: Open 합계가 Open 목록 원장과 같다
      expect(await ledger(gateway, { year: 2026, quarters: [4], forecastOutcome: 'open' })).toEqual(forecast.openTotal)
    })

    it('어느 분기를 골라도 항상 Q1~Q4를 답한다', async () => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when: 분기 없이, Q2로 조회한다
      const whole = await dashboard.summary({ year: 2026 })
      const second = await dashboard.summary({ year: 2026, quarters: [2] })

      // then: 분기 행이 Q1~Q4이고 두 조회가 같다
      expect(whole.quarters.map((q) => q.quarter)).toEqual([1, 2, 3, 4])
      expect(second.quarters).toEqual(whole.quarters)
    })

    it('각 분기가 그 분기 Forecast 요약과 같다', async () => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: Q2를 골라 조회한다
      const { quarters } = await gateway.dashboard.summary({ year: 2026, quarters: [2] })

      // then: 분기마다 셀·Open 합계·합계가 그 분기 Forecast 요약과 같다
      for (const row of quarters) {
        const summary = await gateway.forecast.summary({ year: 2026, quarter: row.quarter })
        for (const column of summary.columns) expect(row.cells[column.key], `Q${row.quarter} ${column.key}`).toEqual(summary.totalRow.cells[column.key])
        expect(row.openTotal).toEqual(summary.totalRow.total)
        const won = summary.totalRow.cells.won ?? { count: 0, amount: 0 }
        expect(row.total).toEqual(sum([summary.totalRow.total, won]))
      }
    })

    it('분기별 합계가 목록 원장과 같다', async () => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: 요약을 조회한다
      const { quarters } = await gateway.dashboard.summary({ year: 2026 })

      // then: 분기 합계가 그 분기 Lost 제외 목록 원장과 같다
      for (const row of quarters) {
        expect(await ledger(gateway, { year: 2026, quarters: [row.quarter], forecastOutcome: 'not_lost' }), `Q${row.quarter}`).toEqual(row.total)
      }
    })

    it('주의 건수는 기간을 무시한다', async () => {
      // given: user 게이트웨이
      const { dashboard } = await make('user')

      // when: 연도, Q1, 아주 옛 연도로 조회한다
      const thisYear = await dashboard.summary({ year: 2026 })
      const quarter = await dashboard.summary({ year: 2026, quarters: [1] })
      const ancient = await dashboard.summary({ year: 1999 })

      // then: 주의 블록이 모두 같다
      expect(quarter.attention).toEqual(thisYear.attention)
      expect(ancient.attention).toEqual(thisYear.attention)
    })

    it('기한초과·미업데이트 건수가 목록의 overdue·stale 건수와 같다', async () => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: 요약을 조회한다
      const { attention } = await gateway.dashboard.summary({ year: 2026 })

      // then: 목록 건수와 같다
      expect(attention.overdue).toBe((await ledger(gateway, { overdue: true })).count)
      expect(attention.stale).toBe((await ledger(gateway, { stale: true })).count)
    })

    it('업무 날짜의 달·분기의 Open Deal을 센다', async () => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: 2020년으로 요약을 조회한다
      const { attention, today } = await gateway.dashboard.summary({ year: 2020 })

      // then: 연·월·분기가 업무 날짜 기준이고 건수가 Open 목록 원장과 같다
      const year = Number(today.slice(0, 4))
      const month = Number(today.slice(5, 7))
      expect(attention.closingThisMonth).toMatchObject({ year, month })
      expect(attention.closingThisQuarter).toMatchObject({ year, quarter: Math.ceil(month / 3) })
      expect(attention.closingThisMonth.count).toBe((await ledger(gateway, { year, month, forecastOutcome: 'open' })).count)
      expect(attention.closingThisQuarter.count).toBe(
        (await ledger(gateway, { year, quarters: [attention.closingThisQuarter.quarter as 1 | 2 | 3 | 4], forecastOutcome: 'open' })).count,
      )
    })

    it('경고 기준의 미업데이트 기준일을 알린다', async () => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: 요약을 조회한다
      const { attention } = await gateway.dashboard.summary({ year: 2026 })

      // then: staleDays가 경고 기준과 같다
      expect(attention.staleDays).toBe((await gateway.alerts.get()).staleDays)
    })

    it('담당자 한 명으로 좁히면 주의 건수도 같은 담당자만 센다', async () => {
      // given: user 게이트웨이와 2026년 Deal의 담당자
      const gateway = await make('user')
      const all = await gateway.dashboard.summary({ year: 2026 })
      const owners = (await gateway.deals.list({ year: 2026, limit: 200 })).items.map((d) => d.ownerId)
      const ownerId = owners[0]
      if (ownerId === undefined) throw new Error('2026년 Deal이 하나도 없습니다(시드 Deal 필요).')

      // when: 그 담당자로 조회한다
      const mine = await gateway.dashboard.summary({ year: 2026, ownerId })

      // then: Status 합계와 주의 건수가 같은 담당자의 목록 원장과 같다
      expect(mine.statuses.total).toEqual(await ledger(gateway, { year: 2026, ownerId, forecastOutcome: 'not_lost' }))
      expect(mine.attention.overdue).toBe((await ledger(gateway, { ownerId, overdue: true })).count)
      expect(mine.attention.stale).toBe((await ledger(gateway, { ownerId, stale: true })).count)
      expect(mine.statuses.total.count).toBeLessThanOrEqual(all.statuses.total.count)
    })

    it('Drill-down이 보내는 Forecast key 집합의 목록 원장과 같다', async () => {
      // given: user 게이트웨이와 Q4 조건
      const gateway = await make('user')
      const query: DashboardQuery = { year: 2026, quarters: [4] }

      // when: 요약을 조회하고 응답 열에서 key 집합을 만든다
      const { statuses, forecast, quarters } = await gateway.dashboard.summary(query)
      const sets = keySets(forecast.columns)

      // then: Status·합계·Open 합계·분기 행이 key 집합 목록 원장과 같다
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

    it('이번 달·이번 분기 건수가 Open key 집합 목록 원장과 같다', async () => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: 2020년으로 요약을 조회하고 Open key 집합을 만든다
      const { attention, today, forecast } = await gateway.dashboard.summary({ year: 2020 })
      const { open } = keySets(forecast.columns)

      // then: 건수가 key 집합 목록 원장과 같다
      const year = Number(today.slice(0, 4))
      const month = Number(today.slice(5, 7))
      expect(attention.closingThisMonth.count).toBe((await ledger(gateway, { year, month, forecastKeys: open })).count)
      expect(attention.closingThisQuarter.count).toBe(
        (await ledger(gateway, { year, quarters: [attention.closingThisQuarter.quarter as 1 | 2 | 3 | 4], forecastKeys: open })).count,
      )
    })

    it('admin이 추가한 Open Forecast 코드가 두 key 집합과 목록 원장에 든다', async () => {
      // given: admin이 Verbal Forecast 코드를 추가했다
      const admin = await make('admin')
      const added = await admin.codes.create({ kind: 'forecast', name: 'Verbal' })

      // when: 요약을 조회한다
      const { forecast } = await admin.dashboard.summary({ year: 2026 })
      const sets = keySets(forecast.columns)

      // then: Verbal이 Open·Lost 제외 집합에 있고 Open 목록 원장이 Open 합계와 같다
      expect(sets.open).toContain(added.key)
      expect(sets.notLost).toContain(added.key)
      expect(await ledger(admin, { year: 2026, forecastKeys: sets.open })).toEqual(forecast.openTotal)
    })

    describe('Quarter 다중 선택', () => {
      it('Forecast 타일은 고른 분기 행 셀의 합이다', async () => {
        // given: user 게이트웨이
        const { dashboard } = await make('user')

        // when: Q1·Q3를 골라 조회한다
        const chosen = await dashboard.summary({ year: 2026, quarters: [1, 3] })

        // then: 타일이 Q1·Q3 행의 합이다
        const rows = chosen.quarters.filter((q) => q.quarter === 1 || q.quarter === 3)
        for (const column of chosen.forecast.columns) {
          expect(chosen.forecast.cells[column.key], column.key).toEqual(sum(rows.map((r) => r.cells[column.key] ?? { count: 0, amount: 0 })))
        }
        expect(chosen.forecast.openTotal).toEqual(sum(rows.map((r) => r.openTotal)))
      })

      it('Status 합계는 고른 분기 합계의 합이다(Lost 제외)', async () => {
        // given: user 게이트웨이
        const { dashboard } = await make('user')

        // when: Q1·Q3를 골라 조회한다
        const chosen = await dashboard.summary({ year: 2026, quarters: [1, 3] })

        // then: Status 합계가 Q1·Q3 합계의 합이다
        expect(chosen.statuses.total).toEqual(sum(chosen.quarters.filter((q) => q.quarter === 1 || q.quarter === 3).map((q) => q.total)))
      })

      it('어느 분기를 골라도 분기 행 네 개와 주의 건수는 그대로다', async () => {
        // given: user 게이트웨이
        const { dashboard } = await make('user')

        // when: 분기 없이, Q1·Q3로 조회한다
        const whole = await dashboard.summary({ year: 2026 })
        const chosen = await dashboard.summary({ year: 2026, quarters: [1, 3] })

        // then: 분기 행과 주의 블록이 같다
        expect(chosen.quarters).toEqual(whole.quarters)
        expect(chosen.attention).toEqual(whole.attention)
      })

      it('여러 분기를 기간에 오름차순으로 알린다', async () => {
        // given: user 게이트웨이
        const { dashboard } = await make('user')

        // when: Q3, Q1 순서로 조회한다
        const { period } = await dashboard.summary({ year: 2026, quarters: [3, 1] })

        // then: quarters는 [1, 3], 범위는 01-01~09-30이다
        expect(period).toEqual({ year: 2026, quarter: null, quarters: [1, 3], from: '2026-01-01', to: '2026-09-30' })
      })

      it('넷 다는 분기 없음과 같다', async () => {
        // given: user 게이트웨이
        const { dashboard } = await make('user')

        // when: 분기 1~4로, 분기 없이 조회한다
        const four = await dashboard.summary({ year: 2026, quarters: [1, 2, 3, 4] })
        const none = await dashboard.summary({ year: 2026 })

        // then: 기간·Status·Forecast가 같다
        expect(four.period).toEqual(none.period)
        expect(four.period.quarters).toEqual([])
        expect(four.statuses).toEqual(none.statuses)
        expect(four.forecast).toEqual(none.forecast)
      })

      it('같은 여러 분기의 목록 원장과 같다', async () => {
        // given: user 게이트웨이와 Q1·Q3 조건
        const gateway = await make('user')
        const query = { year: 2026, quarters: [1, 3] } as const

        // when: 요약을 조회하고 key 집합을 만든다
        const { statuses, forecast } = await gateway.dashboard.summary(query)
        const sets = keySets(forecast.columns)

        // then: Status 합계·Open 합계·Status 항목이 같은 분기 목록 원장과 같다
        expect(await ledger(gateway, { ...query, forecastKeys: sets.notLost })).toEqual(statuses.total)
        expect(await ledger(gateway, { ...query, forecastKeys: sets.open })).toEqual(forecast.openTotal)
        for (const item of statuses.items) expect(await ledger(gateway, { ...query, statusKey: item.key, forecastKeys: sets.notLost }), item.key).toEqual(cellOf(item))
      })

      it.each([[[0]], [[1, 7]], [[1, 2, 3, 4, 1]]])('분기 %j은 422로 거절한다', async (quarters) => {
        // given: user 게이트웨이
        const { dashboard } = await make('user')

        // when·then: 범위 밖 분기나 5개 이상으로 조회하면 422다
        await expectRejects(dashboard.summary({ year: 2026, quarters: quarters as never }), 422)
      })
    })
  })
}
