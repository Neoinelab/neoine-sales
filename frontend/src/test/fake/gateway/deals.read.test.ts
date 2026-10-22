import { describe, expect, it } from 'vitest'
import { seedVendorId } from '../../fixtures/vendors'
import type { DealRow } from '../../../shared/model/types'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const codes = (items: { code: string }[]) => items.map((d) => d.code).sort()
const dealInputFor = (revenueDate: string) => dealInput(USER_ID.kim, { revenueDate })
const codesOf = (...nos: number[]) => nos.map(dealCode).sort()

describe('deals.updatedPeriods', () => {
  it('로그인한 누구나 Fake 시계의 오늘 기준 프리셋 다섯 개를 받는다', async () => {
    const { gateway, control } = await mockAs('han')

    const result = await gateway.deals.updatedPeriods()

    expect(result.today).toBe(control.now().slice(0, 10))
    expect(result.periods.map((p) => p.key)).toEqual(['2w', '1m', '2m', '3m', '6m'])
    for (const period of result.periods) expect(period.to).toBe(result.today)
    expect(result.upcoming.map((p) => p.key)).toEqual(['1m', '2m'])
    for (const period of result.upcoming) expect(period.from).toBe(result.today)
  })

  it('로그인하지 않으면 401이다', async () => {
    const { gateway } = await mockAs('han')
    await gateway.auth.logout()
    await expectApiError(gateway.deals.updatedPeriods(), 401)
  })
})

describe('deals.list', () => {
  it('T-GW 기본 정렬은 최종 업데이트 내림차순이고 페이지 크기는 20이다', async () => {
    const { gateway } = await mockAs('han')
    const page1 = await gateway.deals.list({})
    const page2 = await gateway.deals.list({ offset: 20 })
    expect(page1.items).toHaveLength(20)
    expect(page2.items).toHaveLength(4)
    expect(page2).toMatchObject({ total: 24, offset: 20, limit: 20 })
    const times = [...page1.items, ...page2.items].map((d) => Date.parse(d.lastUpdatedAt))
    expect(times).toEqual([...times].sort((a, b) => b - a))
  })

  it('키워드는 Deal 이름·고객사·파트너사·code를 대소문자 무시로 찾는다', async () => {
    const { gateway } = await mockAs('kim')
    expect(codes((await gateway.deals.list({ keyword: '한빛' })).items)).toEqual(codesOf(1, 13, 23))
    expect(codes((await gateway.deals.list({ keyword: 'itdr' })).items)).toEqual(codesOf(1, 15, 22))
    expect(codes((await gateway.deals.list({ keyword: '시큐어원' })).items)).toEqual(codesOf(4, 10, 18, 23))
    expect(codes((await gateway.deals.list({ keyword: dealCode(9).toLowerCase() })).items)).toEqual(codesOf(9))
    expect((await gateway.deals.list({ keyword: '없는검색어' })).total).toBe(0)
  })

  it('담당자·Vendor·Status·Forecast·내 딜 필터', async () => {
    const { gateway } = await mockAs('kim')
    const mine = await gateway.deals.list({ mine: true })
    expect(codes(mine.items)).toEqual(codesOf(1, 2, 7, 11, 13, 16, 20, 24))
    expect(codes((await gateway.deals.list({ ownerId: USER_ID.kim })).items)).toEqual(codes(mine.items))
    expect((await gateway.deals.list({ vendorId: seedVendorId('Silverfort') })).total).toBe(7)
    expect(codes((await gateway.deals.list({ forecastKey: 'won' })).items)).toEqual(codesOf(11, 12, 24))
    expect(codes((await gateway.deals.list({ forecastKey: 'lost' })).items)).toEqual(codesOf(16))
    expect((await gateway.deals.list({ statusKey: 'contract_completed' })).total).toBe(3)
    expect((await gateway.deals.list({ ownerId: USER_ID.old })).total).toBe(1)
  })

  it('AC-16 Vendor 필터는 id가 같은 Deal만, 없는 id는 0건이다', async () => {
    const { gateway } = await mockAs('kim')

    expect((await gateway.deals.list({ vendorId: seedVendorId('Silverfort') })).total).toBe(7)
    expect((await gateway.deals.list({ vendorId: NO_SUCH_ID })).total).toBe(0)
  })

  it('AC-14 Solution 필터는 대소문자 무시 부분 일치 텍스트이고 Vendor와 AND다', async () => {
    const { gateway } = await mockAs('kim')
    const silverfort = seedVendorId('Silverfort')

    expect((await gateway.deals.list({ solution: 'itdr' })).total).toBe(4)
    expect((await gateway.deals.list({ solution: '  MF  ' })).total).toBe(3)
    expect((await gateway.deals.list({ vendorId: silverfort, solution: 'itdr' })).total).toBe(4)
    expect((await gateway.deals.list({ vendorId: seedVendorId('Okta'), solution: 'itdr' })).total).toBe(0)
    expect((await gateway.deals.list({ solution: '   ' })).total).toBe((await gateway.deals.list({})).total)
    expect((await gateway.deals.list({ solution: 'no-such-text' })).total).toBe(0)
  })

  it('AC-19 분기만 고르면 Fake 시계의 올해 그 분기이다(작년 같은 분기는 제외)', async () => {
    const { gateway } = await mockAs('kim') // Fake 시계 2026-10-15
    const created = await gateway.deals.create({
      ...dealInputFor('2025-11-15'),
    })
    const quarterOnly = (await gateway.deals.list({ quarter: 4, limit: 100 })).items
    const thisYear = (await gateway.deals.list({ year: 2026, quarter: 4, limit: 100 })).items

    expect(quarterOnly.map((d) => d.code).sort()).toEqual(thisYear.map((d) => d.code).sort())
    expect(quarterOnly.map((d) => d.code)).not.toContain(created.code)
    const lastYear = (await gateway.deals.list({ year: 2025, quarter: 4, limit: 100 })).items
    expect(lastYear.map((d) => d.code)).toContain(created.code)
  })

  it('연도·분기 필터는 Expected Close 기준이고 경계를 포함한다', async () => {
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const q4 = (await gateway.deals.list({ year: 2026, quarter: 4, limit: 100 })).items
    expect(q4.length).toBeGreaterThan(0)
    for (const d of q4) expect(d.revenueDate >= '2026-10-01' && d.revenueDate <= '2026-12-31').toBe(true)
    const byYear = (await gateway.deals.list({ year: 2026, limit: 100 })).items
    let sum = 0
    for (const quarter of [1, 2, 3, 4] as const) {
      sum += (await gateway.deals.list({ year: 2026, quarter, limit: 100 })).total
    }
    expect(sum).toBe(byYear.length)
    expect(all.length).toBeGreaterThan(byYear.length)
  })

  it('P6 월 필터는 그 달 1일~말일(양끝 포함)의 Deal만 돌려준다', async () => {
    const { gateway } = await mockAs('kim')
    const first = await gateway.deals.create({ ...dealInputFor('2028-02-01') })
    const last = await gateway.deals.create({ ...dealInputFor('2028-02-29') })
    await gateway.deals.create({ ...dealInputFor('2028-01-31') })
    await gateway.deals.create({ ...dealInputFor('2028-03-01') })

    const found = await gateway.deals.list({ year: 2028, month: 2, limit: 100 })

    expect(found.items.map((d) => d.code).sort()).toEqual([first.code, last.code].sort())
    expect(found.total).toBe(2)
  })

  it('P6 월만 고르면 Fake 시계의 올해 그 달이다', async () => {
    const { gateway } = await mockAs('kim') // Fake 시계 2026-10-15
    const mine = await gateway.deals.create({ ...dealInputFor('2026-03-15') })
    const lastYear = await gateway.deals.create({ ...dealInputFor('2025-03-15') })

    const found = (await gateway.deals.list({ month: 3, limit: 100 })).items.map((d) => d.code)

    expect(found).toContain(mine.code)
    expect(found).not.toContain(lastYear.code)
  })

  it('P6 분기와 월을 함께 주면 422다', async () => {
    const { gateway } = await mockAs('kim')
    await expectApiError(gateway.deals.list({ year: 2026, quarter: 1, month: 1 }), 422, 'Quarter와 월은 함께 선택할 수 없습니다.')
  })

  it('P6 서버 한도: limit이 200을 넘으면 422이고 200은 허용된다', async () => {
    const { gateway } = await mockAs('kim')
    await expectApiError(gateway.deals.list({ limit: 201 }), 422)
    expect((await gateway.deals.list({ limit: 200 })).limit).toBe(200)
  })

  it('최종 업데이트 기간은 lastUpdatedAt의 날짜가 양끝 포함 범위 안인 Deal만 돌려준다', async () => {
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const days = [...new Set(all.map((d) => d.lastUpdatedAt.slice(0, 10)))].sort()
    expect(days.length).toBeGreaterThan(2) // 시드가 날짜를 가르는 기준이 되어야 한다
    const [first, middle, last] = [days[0]!, days[Math.floor(days.length / 2)]!, days[days.length - 1]!]
    const dayOf = (d: { lastUpdatedAt: string }) => d.lastUpdatedAt.slice(0, 10)

    const exact = await gateway.deals.list({ updatedFrom: middle, updatedTo: middle, limit: 100 })
    const since = await gateway.deals.list({ updatedFrom: middle, limit: 100 })
    const until = await gateway.deals.list({ updatedTo: middle, limit: 100 })
    const everything = await gateway.deals.list({ updatedFrom: first, updatedTo: last, limit: 100 })

    expect(codes(exact.items)).toEqual(codes(all.filter((d) => dayOf(d) === middle)))
    expect(exact.total).toBeGreaterThan(0)
    expect(codes(since.items)).toEqual(codes(all.filter((d) => dayOf(d) >= middle)))
    expect(codes(until.items)).toEqual(codes(all.filter((d) => dayOf(d) <= middle)))
    expect(since.total).toBeLessThan(all.length)
    expect(until.total).toBeLessThan(all.length)
    expect(everything.total).toBe(all.length)
  })

  it('최종 업데이트 기간의 시작이 끝보다 늦으면 422로 거절한다', async () => {
    const { gateway } = await mockAs('kim')
    await expectApiError(gateway.deals.list({ updatedFrom: '2026-07-01', updatedTo: '2026-06-30' }), 422)
  })

  it('최종 업데이트 기간은 연도·분기와 AND로 결합한다', async () => {
    const { gateway } = await mockAs('kim')
    const q4 = (await gateway.deals.list({ year: 2026, quarter: 4, limit: 100 })).items
    const day = q4[0]!.lastUpdatedAt.slice(0, 10)

    const both = await gateway.deals.list({ year: 2026, quarter: 4, updatedFrom: day, updatedTo: day, limit: 100 })

    expect(codes(both.items)).toEqual(codes(q4.filter((d) => d.lastUpdatedAt.slice(0, 10) === day)))
  })

  it('정렬: 금액 내림차순, 이름 오름차순, Status 순서', async () => {
    const { gateway } = await mockAs('kim')
    const byAmount = await gateway.deals.list({ sort: 'revenueAmount', order: 'desc' })
    expect(byAmount.items[0]?.code).toBe(dealCode(1))
    expect(byAmount.items[1]?.code).toBe(dealCode(10))
    const asc = (await gateway.deals.list({ sort: 'revenueAmount', order: 'asc' })).items
    expect(asc[0]?.code).toBe(dealCode(24))
    const names = (await gateway.deals.list({ sort: 'name', order: 'asc', limit: 100 })).items.map((d) => d.name)
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, 'ko')))
    const status = (await gateway.deals.list({ sort: 'statusKey', order: 'asc', limit: 100 })).items
    expect(status[0]?.statusKey).toBe('prospecting')
    expect(status[status.length - 1]?.statusKey).toBe('contract_completed')
  })

  it('AC-7 BANT Label 목록 필터는 없다: bantLabelIds를 줘도 조건이 되지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const d1 = await gateway.deals.get(dealCode(1))
    const budget = d1.bant.budget
    if (!budget) throw new Error('Deal 1은 Budget을 선택해야 한다')
    const all = await gateway.deals.list({ limit: 100 })

    const withOldKey = await gateway.deals.list({ limit: 100, bantLabelIds: { budget } } as never)

    expect(withOldKey.total).toBe(all.total)
  })

  it('AC-10 overdue는 risk가 overdue·overdue_stale인 Deal만, stale은 stale·overdue_stale인 Deal만 돌려주고 total이 맞다', async () => {
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const overdue = all.filter((d) => d.risk === 'overdue' || d.risk === 'overdue_stale')
    const stale = all.filter((d) => d.risk === 'stale' || d.risk === 'overdue_stale')
    expect(overdue.length).toBeGreaterThan(0)
    expect(overdue.length).toBeLessThan(all.length)
    expect(stale.length).toBeGreaterThan(0)
    expect(stale.length).toBeLessThan(all.length)

    const foundOverdue = await gateway.deals.list({ overdue: true, limit: 100 })
    const foundStale = await gateway.deals.list({ stale: true, limit: 100 })

    expect(codes(foundOverdue.items)).toEqual(codes(overdue))
    expect(foundOverdue.total).toBe(overdue.length)
    expect(codes(foundStale.items)).toEqual(codes(stale))
    expect(foundStale.total).toBe(stale.length)
  })

  it('AC-10 둘 다 켜면 어느 하나라도 해당하는 Deal이고 Won·Lost는 어느 쪽에도 걸리지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const either = all.filter((d) => d.risk !== null)

    const found = await gateway.deals.list({ overdue: true, stale: true, limit: 100 })

    expect(codes(found.items)).toEqual(codes(either))
    expect(found.total).toBe(either.length)
    for (const d of found.items) expect(['won', 'lost']).not.toContain(d.forecastKey)
  })

  it('AC-10 위험 필터는 다른 조건과 AND이다', async () => {
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const risky = all.filter((d) => d.risk !== null)
    const mineRisky = risky.filter((d) => d.ownerId === USER_ID.kim)
    expect(mineRisky.length).toBeGreaterThan(0)
    expect(mineRisky.length).toBeLessThan(risky.length)

    const found = await gateway.deals.list({ mine: true, overdue: true, stale: true, limit: 100 })

    expect(codes(found.items)).toEqual(codes(mineRisky))
    expect(found.total).toBe(mineRisky.length)
  })

  it('AC-10 total은 페이지와 무관하게 필터 결과 전체를 센다', async () => {
    const { gateway } = await mockAs('kim')
    const risky = (await gateway.deals.list({ limit: 100 })).items.filter((d) => d.risk !== null)
    expect(risky.length).toBeGreaterThan(1)

    const page = await gateway.deals.list({ overdue: true, stale: true, limit: 1 })

    expect(page.items).toHaveLength(1)
    expect(page.total).toBe(risky.length)
  })

  it('AC-10 위험 필터를 끄면 아무 조건도 아니다', async () => {
    const { gateway } = await mockAs('kim')
    const all = await gateway.deals.list({ limit: 100 })

    const off = await gateway.deals.list({ overdue: false, stale: false, limit: 100 })

    expect(off.total).toBe(all.total)
  })

  it('AC-3·4 새 정렬: 담당자·고객사·파트너사·Vendor는 소문자 기준 오름차순·내림차순이고 동률은 code 오름차순이다', async () => {
    const { gateway } = await mockAs('kim')
    const key: Record<'owner' | 'customer' | 'partner' | 'vendor', (d: DealRow) => string> = {
      owner: (d) => d.owner.name,
      customer: (d) => d.customer.company,
      partner: (d) => d.activePartner?.company ?? '',
      vendor: (d) => d.vendor?.name ?? '',
    }
    for (const sort of ['owner', 'customer', 'partner', 'vendor'] as const) {
      for (const order of ['asc', 'desc'] as const) {
        const rows = (await gateway.deals.list({ sort, order, limit: 100 })).items
        const present = rows.filter((d) => key[sort](d) !== '')
        for (let i = 1; i < present.length; i++) {
          const prev = key[sort](present[i - 1]!).toLowerCase()
          const next = key[sort](present[i]!).toLowerCase()
          if (prev === next) expect(present[i - 1]!.code < present[i]!.code).toBe(true)
          else expect(order === 'asc' ? prev < next : prev > next).toBe(true)
        }
      }
    }
  })

  it('AC-4 파트너나 Vendor가 없는 Deal은 오름차순·내림차순 모두 맨 뒤다', async () => {
    const { gateway } = await mockAs('kim')
    const rows = (await gateway.deals.list({ limit: 100 })).items
    expect(rows.some((d) => d.activePartner === null)).toBe(true)
    const noVendor = await gateway.deals.create(dealInput(USER_ID.kim, { name: '벤더 없는 Deal', vendorId: null }))
    expect(noVendor.vendor).toBeNull()

    for (const order of ['asc', 'desc'] as const) {
      const byPartner = (await gateway.deals.list({ sort: 'partner', order, limit: 100 })).items
      const firstAbsent = byPartner.findIndex((d) => d.activePartner === null)
      expect(byPartner.slice(firstAbsent).every((d) => d.activePartner === null)).toBe(true)
      expect(byPartner.slice(0, firstAbsent).every((d) => d.activePartner !== null)).toBe(true)
      const byVendor = (await gateway.deals.list({ sort: 'vendor', order, limit: 100 })).items
      const firstNoVendor = byVendor.findIndex((d) => d.vendor === null)
      expect(firstNoVendor).toBeGreaterThanOrEqual(0)
      expect(byVendor.slice(firstNoVendor).every((d) => d.vendor === null)).toBe(true)
      expect(byVendor.slice(0, firstNoVendor).every((d) => d.vendor !== null)).toBe(true)
    }
  })

  it('AC-4 Forecast 정렬은 Forecast 코드의 현재 순서다', async () => {
    const { gateway } = await mockAs('kim')
    const order = (await gateway.codes.all()).forecasts.map((c) => c.key)
    for (const dir of ['asc', 'desc'] as const) {
      const rows = (await gateway.deals.list({ sort: 'forecastKey', order: dir, limit: 100 })).items
      const positions = rows.map((d) => order.indexOf(d.forecastKey))
      expect(positions).toEqual([...positions].sort((a, b) => (dir === 'asc' ? a - b : b - a)))
    }
  })

  it('정렬은 페이지 전체에 적용된다: 2페이지는 1페이지 다음 순서다', async () => {
    const { gateway } = await mockAs('kim')
    const whole = (await gateway.deals.list({ sort: 'owner', order: 'asc', limit: 100 })).items.map((d) => d.code)
    const first = (await gateway.deals.list({ sort: 'owner', order: 'asc', offset: 0, limit: 10 })).items.map((d) => d.code)
    const second = (await gateway.deals.list({ sort: 'owner', order: 'asc', offset: 10, limit: 10 })).items.map((d) => d.code)

    expect([...first, ...second]).toEqual(whole.slice(0, 20))
  })

  it('행에는 파생값이 채워진다(고객·활성 파트너·Next Action·퇴사자 Owner)', async () => {
    const { gateway } = await mockAs('han')
    const rows = (await gateway.deals.list({ limit: 100 })).items
    const d1 = rows.find((d) => d.code === dealCode(1))
    expect(d1).toMatchObject({
      customer: { company: '한빛은행', name: '정민수' },
      activePartner: { company: '에이원시스템', name: '표성호' },
      nextAction: { text: '계약서 초안 검토', dueDate: '2026-10-18', status: 'open' },
      owner: { name: '김영업' },
    })
    expect(rows.find((d) => d.code === dealCode(5))?.activePartner).toBeNull()
    expect(rows.find((d) => d.code === dealCode(4))?.lastUpdatedAt.slice(0, 10)).toBe('2026-09-24')
    expect(rows.find((d) => d.code === dealCode(23))?.owner.status).toBe('resigned')
  })

  it('반환 객체를 바꿔도 저장소는 영향받지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const row = (await gateway.deals.list({})).items[0]
    if (!row) throw new Error('empty')
    row.name = '변조'
    row.customer.company = '변조'
    const again = await gateway.deals.get(row.code)
    expect(again.name).not.toBe('변조')
    expect(again.customer.company).not.toBe('변조')
  })
})

describe('deals.get / impact', () => {
  it('없는 code는 404', async () => {
    const { gateway } = await mockAs('kim')
    await expectApiError(gateway.deals.get('20000101-ZZZZ'), 404, 'Deal을 찾을 수 없습니다.')
    await expectApiError(gateway.deals.impact('20000101-ZZZZ'), 404)
  })

  it('impact는 연쇄 삭제 건수와 목록 건수가 같다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const impact = await gateway.deals.impact(code)
    expect(impact.historyCount).toBe((await gateway.history.list(code, {})).length)
    expect(impact.actionCount).toBe((await gateway.actions.list(code, {})).length)
    expect(impact.attachmentCount).toBe(3)
  })
})
