import { describe, expect, it } from 'vitest'
import type { ForecastQuery } from '../../shared/model/types'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'

type Gw = Awaited<ReturnType<typeof mockAs>>['gateway']

/** Deal 원장(목록)에서 직접 합산한 값. summary와 같아야 한다. */
async function ledger(gw: Gw, query: ForecastQuery) {
  const items = (await gw.deals.list({ ...query, limit: 1000 })).items
  const sum = (filter: (d: (typeof items)[number]) => boolean) => {
    const rows = items.filter(filter)
    return { count: rows.length, amount: rows.reduce((s, d) => s + d.revenueAmount, 0) }
  }
  return { items, sum }
}

describe('forecast.summary', () => {
  it('T-FC-02 열은 Forecast 코드 순서이고 Lost는 제외된다', async () => {
    const { gateway } = await mockAs('han')
    const summary = await gateway.forecast.summary({ year: 2026 })
    expect(summary.columns.map((c) => c.key)).toEqual(['pipeline', 'best', 'most_likely', 'commit', 'won'])
    expect(summary.columns.map((c) => c.outcome)).toEqual(['open', 'open', 'open', 'open', 'won'])
    expect(summary.vendors).toContain('Silverfort')
    expect(summary.query).toEqual({ year: 2026 })
  })

  it('T-FC-03 담당자별 행(퇴사자 포함)과 Total은 Open 합(Won·Lost 제외)이다', async () => {
    const { gateway } = await mockAs('kim')
    const summary = await gateway.forecast.summary({ year: 2026 })
    const next = await gateway.forecast.summary({ year: 2027, quarter: 1 }) // Deal 23(퇴사자 Owner)은 2027-Q1
    expect(next.rows.map((r) => r.ownerName)).toContain('강퇴사(퇴사)')
    for (const row of [...summary.rows, summary.totalRow]) {
      const open = ['pipeline', 'best', 'most_likely', 'commit'].map((k) => row.cells[k] ?? { count: 0, amount: 0 })
      expect(row.total.count).toBe(open.reduce((s, c) => s + c.count, 0))
      expect(row.total.amount).toBe(open.reduce((s, c) => s + c.amount, 0))
      for (const col of summary.columns) expect(row.cells[col.key]).toBeDefined()
    }
    expect(summary.totalRow).toMatchObject({ ownerId: null, ownerName: '합계' })
  })

  it('T-FC-05 합계는 Deal 원장 합과 일치한다(연도, 분기, Vendor, 담당자 조합)', async () => {
    const { gateway } = await mockAs('kim')
    const queries: ForecastQuery[] = [
      { year: 2026 },
      { year: 2026, quarter: 4 },
      { year: 2027, quarter: 1 },
      { year: 2026, vendor: 'Silverfort' },
      { year: 2026, quarter: 4, ownerId: 'u-kim' },
    ]
    for (const query of queries) {
      const summary = await gateway.forecast.summary(query)
      const { sum } = await ledger(gateway, query)
      for (const col of summary.columns) {
        expect(summary.totalRow.cells[col.key]).toEqual(sum((d) => d.forecastKey === col.key))
        for (const row of summary.rows) {
          expect(row.cells[col.key]).toEqual(sum((d) => d.forecastKey === col.key && d.owner.id === row.ownerId))
        }
      }
      expect(summary.totalRow.total).toEqual(sum((d) => d.forecastKey !== 'won' && d.forecastKey !== 'lost'))
      expect(summary.rows.reduce((s, r) => s + r.total.amount, 0)).toBe(summary.totalRow.total.amount)
    }
  })

  it('T-FC-01 분기 경계: 12/31은 Q4, 1/1은 다음 해 Q1', async () => {
    const { gateway } = await mockAs('kim')
    const dec = await gateway.deals.create(dealInput('u-kim', { name: '경계 12/31', revenueDate: '2028-12-31', forecastKey: 'commit', revenueAmount: 7_000_000 }))
    const jan = await gateway.deals.create(dealInput('u-kim', { name: '경계 1/1', revenueDate: '2029-01-01', forecastKey: 'best', revenueAmount: 3_000_000 }))
    const y2028 = await gateway.forecast.summary({ year: 2028 })
    expect(y2028.totalRow.cells.commit).toEqual({ count: 1, amount: 7_000_000 })
    expect(y2028.totalRow.cells.best).toEqual({ count: 0, amount: 0 })
    const q4 = await gateway.forecast.summary({ year: 2028, quarter: 4 })
    expect(q4.totalRow.cells.commit?.count).toBe(1)
    const q3 = await gateway.forecast.summary({ year: 2028, quarter: 3 })
    expect(q3.totalRow.cells.commit?.count).toBe(0)
    expect(q3.rows).toEqual([])
    const y2029q1 = await gateway.forecast.summary({ year: 2029, quarter: 1 })
    expect(y2029q1.totalRow.cells.best).toEqual({ count: 1, amount: 3_000_000 })
    expect([dec.code, jan.code]).toHaveLength(2)
  })

  it('Lost Deal은 어떤 열에도 합산되지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const d16 = await gateway.deals.get(dealCode(16))
    const before = await gateway.forecast.summary({ year: Number(d16.revenueDate.slice(0, 4)) })
    const total = Object.values(before.totalRow.cells).reduce((s, c) => s + c.count, 0)
    const { items } = await ledger(gateway, { year: Number(d16.revenueDate.slice(0, 4)) })
    expect(total).toBe(items.filter((d) => d.forecastKey !== 'lost').length)
  })

  it('Forecast 변경은 요약에 즉시 반영된다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const deal = await gateway.deals.get(code)
    const query = { year: Number(deal.revenueDate.slice(0, 4)), ownerId: 'u-kim' }
    const before = await gateway.forecast.summary(query)
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'best' } })
    const after = await gateway.forecast.summary(query)
    expect(after.totalRow.cells.commit?.count).toBe((before.totalRow.cells.commit?.count ?? 0) - 1)
    expect(after.totalRow.cells.best?.count).toBe((before.totalRow.cells.best?.count ?? 0) + 1)
  })

  it('로그인이 필요하다', async () => {
    const { gateway } = await mockAs(null)
    await expectApiError(gateway.forecast.summary({ year: 2026 }), 401)
  })
})
