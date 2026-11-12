/**
 * Forecast 요약 계약. mock과 실제 서버가 같은 결과를 내야 한다.
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
    // 테스트 코드: FC-047
    it.each(['admin', 'sales', 'user'] as const)('%s 역할도 요약을 읽는다', async (role) => {
      // given: 해당 역할로 로그인한 게이트웨이
      const gateway = await make(role)

      // when: 요약을 읽는다
      const summary = await gateway.forecast.summary({ year: 2026 })

      // then: 열이 있다
      expect(summary.columns.length).toBeGreaterThan(0)
    })

    // 테스트 코드: FC-050
    it('열은 Lost를 뺀 Forecast 코드를 코드 순서로 나열한다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when: 요약을 읽는다
      const { columns } = await forecast.summary({ year: 2026 })

      // then: lost가 없고 outcome이 open·won이며 order가 오름차순이다
      expect(columns.map((c) => c.key)).not.toContain('lost')
      expect(columns.every((c) => c.outcome === 'open' || c.outcome === 'won')).toBe(true)
      const orders = columns.map((c) => c.order)
      expect(orders).toEqual([...orders].sort((a, b) => a - b))
      expect(columns.map((c) => c.key)).toEqual(expect.arrayContaining(['pipeline', 'best', 'most_likely', 'commit', 'won']))
    })

    // 테스트 코드: FC-050
    it('모든 행과 합계 행에 열마다 셀이 있다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when: 요약을 읽는다
      const summary = await forecast.summary({ year: 2026 })

      // then: 모든 행의 셀이 열마다 있다
      for (const row of [...summary.rows, summary.totalRow]) {
        for (const column of summary.columns) expect(row.cells[column.key]).toBeDefined()
      }
    })

    // 테스트 코드: FC-050
    it('Total은 Open 셀의 합이고 Won·Lost를 포함하지 않는다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when: 요약을 읽는다
      const summary = await forecast.summary({ year: 2026 })

      // then: 각 행의 Total이 Open 셀 합이다
      for (const row of [...summary.rows, summary.totalRow]) {
        const open = openKeys(summary).map((key) => row.cells[key] ?? { count: 0, amount: 0 })
        expect(row.total).toEqual({
          count: open.reduce((sum, cell) => sum + cell.count, 0),
          amount: open.reduce((sum, cell) => sum + cell.amount, 0),
        })
      }
    })

    it('합계 행은 행의 합과 셀마다 같다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when: 요약을 읽는다
      const summary = await forecast.summary({ year: 2026 })

      // then: 합계 행 셀이 행 셀의 합이다
      for (const column of summary.columns) {
        const count = summary.rows.reduce((sum, row) => sum + (row.cells[column.key]?.count ?? 0), 0)
        const amount = summary.rows.reduce((sum, row) => sum + (row.cells[column.key]?.amount ?? 0), 0)
        expect(summary.totalRow.cells[column.key]).toEqual({ count, amount })
      }
    })

    // 테스트 코드: FC-050
    it.each<[string, ForecastQuery]>([
      ['year', { year: 2026 }],
      ['quarter', { year: 2026, quarter: 4 }],
      ['month', { year: 2026, month: 11 }],
      ['next january', { year: 2027, month: 1 }],
    ])('%s 조건에서 Lost를 뺀 Deal 목록(원장) 합과 같다', async (_name, query) => {
      // given: user 게이트웨이
      const gateway = await make('user')

      // when: 요약과 같은 조건의 Deal 목록을 읽는다
      const summary = await gateway.forecast.summary(query)
      const deals = (await ledger(gateway, query)).filter((d) => d.forecastKey !== 'lost')

      // then: 합계 행의 Open 합과 Won 셀이 원장 합과 같다
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

    it('ownerId를 주면 그 담당자만 남는다', async () => {
      // given: 전체 요약의 첫 행 담당자
      const gateway = await make('user')
      const all = await gateway.forecast.summary({ year: 2026 })
      const first = all.rows[0]
      if (!first) throw new Error('담당자 행이 하나도 없습니다(시드 Deal 필요).')

      // when: 그 담당자 조건으로 요약을 읽는다
      const mine = await gateway.forecast.summary({ year: 2026, ownerId: first.ownerId ?? 0 })

      // then: 그 담당자 행만 있다
      expect(mine.rows.map((r) => r.ownerId)).toEqual([first.ownerId])
    })

    it('basis live와 서버 시각(asOf)을 돌려준다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when: 요약을 읽는다
      const summary = await forecast.summary({ year: 2026 })

      // then: basis live이고 asOf가 시각이다
      expect(summary.basis).toBe('live')
      expect(Number.isNaN(Date.parse(summary.asOf))).toBe(false)
    })

    it('분기와 월을 함께 주면 422다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when·then: quarter=1&month=1로 읽으면 안내 문구의 422다
      await expectRejects(forecast.summary({ year: 2026, quarter: 1, month: 1 }), 422, QUARTER_MONTH)
    })

    it('실시간 요약에는 기준 월이 없다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when: 요약을 읽는다
      const summary = await forecast.summary({ year: 2026 })

      // then: 기준 월이 null이다
      expect(summary.snapshotPeriod).toBeNull()
    })
  })

  describe('forecast 스냅숏 계약', () => {
    const PERIOD = /^\d{4}-(0[1-9]|1[0-2])$/

    // 테스트 코드: FC-073
    it.each(['admin', 'sales', 'user'] as const)('%s 역할도 스냅숏 목록을 읽는다', async (role) => {
      // given: 해당 역할로 로그인한 게이트웨이
      const gateway = await make(role)

      // when: 스냅숏 목록을 읽는다
      const list = await gateway.forecast.snapshots()

      // then: 목록이다
      expect(Array.isArray(list)).toBe(true)
    })

    it('기준 월(YYYY-MM)과 생성 시각을 최근 순으로 나열한다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when: 스냅숏 목록을 읽는다
      const list = await forecast.snapshots()

      // then: 기준 월 형식과 시각이 맞고 최근 순이다
      for (const item of list) {
        expect(item.period).toMatch(PERIOD)
        expect(Number.isNaN(Date.parse(item.takenAt))).toBe(false)
      }
      const periods = list.map((item) => item.period)
      expect(periods).toEqual([...periods].sort().reverse())
    })

    // 테스트 코드: FC-081
    it('저장된 적 없는 기준 월은 404다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when·then: 없는 기준 월을 읽으면 404다
      await expectRejects(forecast.snapshotSummary('1999-01', { year: 2026 }), 404)
    })

    // 테스트 코드: FC-081
    it.each(['2026-9', 'abc', '2026-13'])('형식이 틀린 기준 월 %j는 404다', async (period) => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when·then: 형식이 틀린 기준 월을 읽으면 404다
      await expectRejects(forecast.snapshotSummary(period, { year: 2026 }), 404)
    })

    it('없는 기준 월이어도 분기와 월 동시(422)를 먼저 판정한다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when·then: 없는 기준 월에 quarter+month를 주면 422다
      await expectRejects(forecast.snapshotSummary('1999-01', { year: 2026, quarter: 1, month: 1 }), 422, QUARTER_MONTH)
    })

    it('목록의 모든 스냅숏을 생성 시각이 찍힌 스냅숏 요약으로 읽는다', async () => {
      // given: user 게이트웨이
      const { forecast } = await make('user')

      // when: 목록의 기준 월마다 요약을 읽는다
      for (const item of await forecast.snapshots()) {
        const summary = await forecast.snapshotSummary(item.period, { year: Number(item.period.slice(0, 4)) })

        // then: basis snapshot, 기준 월, 생성 시각이 맞고 lost 열이 없다
        expect(summary.basis).toBe('snapshot')
        expect(summary.snapshotPeriod).toBe(item.period)
        expect(summary.asOf).toBe(item.takenAt)
        expect(summary.columns.map((c) => c.key)).not.toContain('lost')
      }
    })
  })
}
