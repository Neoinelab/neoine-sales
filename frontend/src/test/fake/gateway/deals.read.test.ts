import { describe, expect, it } from 'vitest'
import { seedSolutionId, seedVendorId } from '../../fixtures/vendors'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const codes = (items: { code: string }[]) => items.map((d) => d.code).sort()
const dealInputFor = (revenueDate: string) => dealInput(USER_ID.kim, { revenueDate })
const codesOf = (...nos: number[]) => nos.map(dealCode).sort()

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

  it('AC-16 Vendor와 Solution 필터는 id가 같은 Deal만 돌려주고 없는 id는 0건이다', async () => {
    const { gateway } = await mockAs('kim')
    const silverfort = seedVendorId('Silverfort')

    expect((await gateway.deals.list({ vendorId: silverfort, solutionId: seedSolutionId('Silverfort', 'ITDR') })).total).toBe(4)
    expect((await gateway.deals.list({ solutionId: seedSolutionId('Silverfort', 'MFA') })).total).toBe(3)
    expect((await gateway.deals.list({ vendorId: NO_SUCH_ID })).total).toBe(0)
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

  it('연도·분기와 기간 필터는 Expected Close 기준이고 경계를 포함한다', async () => {
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
    const target = all[0]
    if (!target) throw new Error('no deals')
    const exact = await gateway.deals.list({ revenueFrom: target.revenueDate, revenueTo: target.revenueDate, limit: 100 })
    expect(exact.items.map((d) => d.code)).toContain(target.code)
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

  it('BANT Label 필터는 구분별 AND다', async () => {
    const { gateway } = await mockAs('kim')
    const d1 = await gateway.deals.get(dealCode(1))
    const budget = d1.bant.budget
    const authority = d1.bant.authority
    if (!budget || !authority) throw new Error('Deal 1은 BANT를 모두 선택해야 한다')
    const one = await gateway.deals.list({ bantLabelIds: { budget } })
    expect(one.items.map((d) => d.code)).toContain(dealCode(1))
    const both = await gateway.deals.list({ bantLabelIds: { budget, authority } })
    for (const d of both.items) expect(d.bant.budget === budget && d.bant.authority === authority).toBe(true)
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
