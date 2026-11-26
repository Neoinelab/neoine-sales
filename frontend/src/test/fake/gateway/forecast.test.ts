import { describe, expect, it } from 'vitest'
import type { SeedFactory } from '..'
import type { ForecastQuery } from '../../../shared/model/types'
import { buildSampleSeed } from '../../fixtures/sampleSeed'
import { seedVendorId } from '../../fixtures/vendors'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

type Gw = Awaited<ReturnType<typeof mockAs>>['gateway']

/** Deal 원장(목록)에서 직접 합산한 값. summary와 같아야 한다. */
async function ledger(gw: Gw, query: ForecastQuery) {
  const { quarter, ...rest } = query
  const items = (await gw.deals.list({ ...rest, ...(quarter ? { quarters: [quarter] } : {}), limit: 200 })).items
  const sum = (filter: (d: (typeof items)[number]) => boolean) => {
    const rows = items.filter(filter)
    return { count: rows.length, amount: rows.reduce((s, d) => s + (d.revenueAmount ?? 0), 0) }
  }
  return { items, sum }
}

describe('forecast.summary', () => {
  it('열은 Forecast 코드 순서이고 Lost는 제외된다', async () => {
    // given: han으로 로그인한 Fake
    const { gateway } = await mockAs('han')
    // when: 2026년 요약을 읽는다
    const summary = await gateway.forecast.summary({ year: 2026 })
    // then: 열이 코드 순서이고 outcome이 맞으며 조건이 그대로 담긴다
    expect(summary.columns.map((c) => c.key)).toEqual(['pipeline', 'best', 'most_likely', 'commit', 'won'])
    expect(summary.columns.map((c) => c.outcome)).toEqual(['open', 'open', 'open', 'open', 'won'])
    expect(summary.query).toEqual({ year: 2026 })
  })

  it('담당자별 행(퇴사자 포함)과 Total은 Open 합(Won·Lost 제외)이다', async () => {
    // given: kim으로 로그인한 Fake
    const { gateway } = await mockAs('kim')
    // when: 2026년 요약과 퇴사자 Owner Deal이 있는 2027 Q1 요약을 읽는다
    const summary = await gateway.forecast.summary({ year: 2026 })
    const next = await gateway.forecast.summary({ year: 2027, quarter: 1 }) // Deal 23(퇴사자 Owner)은 2027-Q1
    // then: 퇴사자 행이 있고 모든 행의 Total은 Open 열의 합이며 합계 행에는 담당자가 없다
    expect(next.rows.map((r) => r.ownerName)).toContain('강퇴사(퇴사)')
    for (const row of [...summary.rows, summary.totalRow]) {
      const open = ['pipeline', 'best', 'most_likely', 'commit'].map((k) => row.cells[k] ?? { count: 0, amount: 0 })
      expect(row.total.count).toBe(open.reduce((s, c) => s + c.count, 0))
      expect(row.total.amount).toBe(open.reduce((s, c) => s + c.amount, 0))
      for (const col of summary.columns) expect(row.cells[col.key]).toBeDefined()
    }
    expect(summary.totalRow).toMatchObject({ ownerId: null, ownerName: '합계' })
  })

  it('합계는 Deal 원장 합과 일치한다 (연도·분기·Vendor·담당자 조합)', async () => {
    // given: kim으로 로그인한 Fake와 여러 조건
    const { gateway } = await mockAs('kim')
    const queries: ForecastQuery[] = [
      { year: 2026 },
      { year: 2026, quarter: 4 },
      { year: 2027, quarter: 1 },
      { year: 2026, vendorId: seedVendorId('Silverfort') },
      { year: 2026, quarter: 4, ownerId: USER_ID.kim },
    ]
    for (const query of queries) {
      // when: 조건마다 요약과 같은 조건의 Deal 목록을 읽는다
      const summary = await gateway.forecast.summary(query)
      const { sum } = await ledger(gateway, query)
      // then: 열·행·합계 행의 셀이 목록의 합과 같다
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

  it('분기 경계: 12/31은 그 해 Q4, 1/1은 다음 해 Q1이다', async () => {
    // given: 12/31 commit Deal과 다음 해 1/1 best Deal
    const { gateway } = await mockAs('kim')
    const dec = await gateway.deals.create(dealInput(USER_ID.kim, { name: '경계 12/31', revenueDate: '2028-12-31', forecastKey: 'commit', revenueAmount: 7_000_000 }))
    const jan = await gateway.deals.create(dealInput(USER_ID.kim, { name: '경계 1/1', revenueDate: '2029-01-01', forecastKey: 'best', revenueAmount: 3_000_000 }))
    // when: 연도·분기별로 요약을 읽는다
    const y2028 = await gateway.forecast.summary({ year: 2028 })
    // then: 12/31 Deal은 2028 Q4에만, 1/1 Deal은 2029 Q1에만 들어간다
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
    // given: Lost Deal이 있는 연도
    const { gateway } = await mockAs('kim')
    const d16 = await gateway.deals.get(dealCode(16))
    // when: 요약과 Deal 목록을 읽는다
    const before = await gateway.forecast.summary({ year: Number(d16.revenueDate.slice(0, 4)) })
    const total = Object.values(before.totalRow.cells).reduce((s, c) => s + c.count, 0)
    const { items } = await ledger(gateway, { year: Number(d16.revenueDate.slice(0, 4)) })
    // then: 요약 건수는 Lost가 아닌 Deal 수와 같다
    expect(total).toBe(items.filter((d) => d.forecastKey !== 'lost').length)
  })

  it('Forecast 변경은 요약에 즉시 반영된다', async () => {
    // given: commit Deal 하나가 있는 담당자의 요약
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const deal = await gateway.deals.get(code)
    const query = { year: Number(deal.revenueDate.slice(0, 4)), ownerId: USER_ID.kim }
    const before = await gateway.forecast.summary(query)
    // when: 그 Deal의 Forecast를 best로 바꾼다
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'best' } })
    const after = await gateway.forecast.summary(query)
    // then: commit은 1건 줄고 best는 1건 늘어난다
    expect(after.totalRow.cells.commit?.count).toBe((before.totalRow.cells.commit?.count ?? 0) - 1)
    expect(after.totalRow.cells.best?.count).toBe((before.totalRow.cells.best?.count ?? 0) + 1)
  })

  it('로그인이 필요하다', async () => {
    // given: 로그인하지 않은 Fake
    const { gateway } = await mockAs(null)
    // when·then: 요약을 읽으면 401이다
    await expectApiError(gateway.forecast.summary({ year: 2026 }), 401)
  })

  it('월 단위는 그 달 1일~말일(양끝 포함)만 집계하고 원장 합과 같다', async () => {
    // given: 2월 말·3월 초·1월 말 Deal
    const { gateway } = await mockAs('kim')
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '2월 말', revenueDate: '2028-02-29', forecastKey: 'commit', revenueAmount: 2_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '3월 초', revenueDate: '2028-03-01', forecastKey: 'commit', revenueAmount: 5_000_000 }))
    await gateway.deals.create(dealInput(USER_ID.kim, { name: '1월 말', revenueDate: '2028-01-31', forecastKey: 'commit', revenueAmount: 9_000_000 }))

    // when: 2028년 2월 요약과 같은 조건의 Deal 목록을 읽는다
    const feb = await gateway.forecast.summary({ year: 2028, month: 2 })
    const { sum } = await ledger(gateway, { year: 2028, month: 2 } as ForecastQuery)

    // then: 2월 Deal만 집계되고 원장 합과 같다
    expect(feb.totalRow.cells.commit).toEqual({ count: 1, amount: 2_000_000 })
    expect(feb.totalRow.cells.commit).toEqual(sum((d) => d.forecastKey === 'commit'))
    expect(feb.query).toEqual({ year: 2028, month: 2 })
  })

  it('Quarter와 월을 함께 주면 422다', async () => {
    // given: kim으로 로그인한 Fake
    const { gateway } = await mockAs('kim')
    // when·then: quarter=1&month=1로 읽으면 안내 문구의 422다
    await expectApiError(gateway.forecast.summary({ year: 2026, quarter: 1, month: 1 }), 422, 'Quarter와 월은 함께 선택할 수 없습니다.')
  })

  it('응답은 basis live와 서버 현재 시각(asOf)을 담는다', async () => {
    // given: kim으로 로그인한 Fake
    const { gateway } = await mockAs('kim')
    // when: 요약을 읽는다
    const summary = await gateway.forecast.summary({ year: 2026 })
    // then: basis live이고 asOf는 오프셋이 있는 시각이다
    expect(summary.basis).toBe('live')
    expect(Number.isNaN(Date.parse(summary.asOf))).toBe(false)
    expect(summary.asOf).toMatch(/(?:[+-]\d{2}:\d{2}|Z)$/)
  })

  it('열은 코드 order를 담고 오름차순이다', async () => {
    // given: kim으로 로그인한 Fake
    const { gateway } = await mockAs('kim')
    // when: 요약을 읽는다
    const { columns } = await gateway.forecast.summary({ year: 2026 })
    // then: order가 정수이고 오름차순이다
    const orders = columns.map((c) => c.order)
    expect(orders.every((o) => Number.isInteger(o))).toBe(true)
    expect(orders).toEqual([...orders].sort((a, b) => a - b))
  })

  it('행 순서는 재직자 먼저, 이름의 문자 코드 순, 이름이 같으면 사용자 id 순이다 (로캘 비교가 아니다)', async () => {
    // given: kim을 "Bob", park을 "alice"로 바꾼 사용자 정보 (문자 코드로는 "B" < "a", 로캘 비교로는 반대)
    const seed: SeedFactory = (clock) => renameUsers(buildSampleSeed(clock), { [USER_ID.kim]: 'Bob', [USER_ID.park]: 'alice' })
    const { gateway } = await mockAs('kim', { seed })

    // when: 2026년 요약을 읽는다
    const rows = (await gateway.forecast.summary({ year: 2026 })).rows.filter((r) => new Set<number>([USER_ID.kim, USER_ID.park]).has(r.ownerId ?? 0))

    // then: 문자 코드 순으로 Bob이 alice보다 앞이다
    expect(rows.map((r) => r.ownerName)).toEqual(['Bob', 'alice'])

    // given: 두 사람의 이름이 같은 사용자 정보
    const sameName: SeedFactory = (clock) => renameUsers(buildSampleSeed(clock), { [USER_ID.kim]: '동명', [USER_ID.park]: '동명' })
    const same = await mockAs('kim', { seed: sameName })

    // when: 다시 읽는다
    const tied = (await same.gateway.forecast.summary({ year: 2026 })).rows.filter((r) => r.ownerName === '동명')

    // then: id 오름차순이다
    expect(tied.map((r) => r.ownerId)).toEqual([USER_ID.kim, USER_ID.park])
  })
})

function renameUsers(data: ReturnType<typeof buildSampleSeed>, names: Record<number, string>): ReturnType<typeof buildSampleSeed> {
  for (const user of data.users) {
    const name = names[user.id]
    if (name !== undefined) user.name = name
  }
  return data
}
