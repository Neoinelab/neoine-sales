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
    // given: 로그인한 사용자(han)
    const { gateway, control } = await mockAs('han')

    // when: 업데이트 기간 프리셋을 읽는다
    const result = await gateway.deals.updatedPeriods()

    // then: 오늘 기준 프리셋 다섯 개와 예정 프리셋 두 개를 받는다
    expect(result.today).toBe(control.now().slice(0, 10))
    expect(result.periods.map((p) => p.key)).toEqual(['2w', '1m', '2m', '3m', '6m'])
    for (const period of result.periods) expect(period.to).toBe(result.today)
    expect(result.upcoming.map((p) => p.key)).toEqual(['1m', '2m'])
    for (const period of result.upcoming) expect(period.from).toBe(result.today)
  })

  it('로그인하지 않으면 401이다', async () => {
    // given: 로그아웃한 상태
    const { gateway } = await mockAs('han')
    await gateway.auth.logout()
    // when·then: 기간 프리셋을 읽는다 → 401이다
    await expectApiError(gateway.deals.updatedPeriods(), 401)
  })
})

describe('deals.list', () => {
  it('T-GW 기본 정렬은 최종 업데이트 내림차순이고 페이지 크기는 20이다', async () => {
    // given: han 로그인
    const { gateway } = await mockAs('han')
    // when: 조건 없이 1·2페이지를 읽는다
    const page1 = await gateway.deals.list({})
    const page2 = await gateway.deals.list({ offset: 20 })
    // then: 최종 업데이트 내림차순이고 페이지 크기는 20이다
    expect(page1.items).toHaveLength(20)
    expect(page2.items).toHaveLength(4)
    expect(page2).toMatchObject({ total: 24, offset: 20, limit: 20 })
    const times = [...page1.items, ...page2.items].map((d) => Date.parse(d.lastUpdatedOn))
    expect(times).toEqual([...times].sort((a, b) => b - a))
  })

  it('키워드는 Deal 이름·고객사·파트너사·code를 대소문자 무시로 찾는다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    // when: 키워드로 검색한다
    const r1 = codes((await gateway.deals.list({ keyword: '한빛' })).items)
    const r2 = codes((await gateway.deals.list({ keyword: 'itdr' })).items)
    const r3 = codes((await gateway.deals.list({ keyword: '시큐어원' })).items)
    const r4 = codes((await gateway.deals.list({ keyword: dealCode(9).toLowerCase() })).items)
    const r5 = (await gateway.deals.list({ keyword: '없는검색어' })).total
    // then: 이름·고객사·파트너사·code를 대소문자 무시로 찾고 없는 검색어는 0건이다
    expect(r1).toEqual(codesOf(1, 13, 23))
    expect(r2).toEqual(codesOf(1, 15, 22))
    expect(r3).toEqual(codesOf(4, 10, 18, 23))
    expect(r4).toEqual(codesOf(9))
    expect(r5).toBe(0)
  })

  it('담당자·Vendor·Status·Forecast·내 딜 필터', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    // when: 담당자·Vendor·Status·Forecast·내 딜 조건으로 검색한다
    const mine = await gateway.deals.list({ mine: true })
    const r1 = codes(mine.items)
    const r2 = codes((await gateway.deals.list({ ownerId: USER_ID.kim })).items)
    const r3 = (await gateway.deals.list({ vendorId: seedVendorId('Silverfort') })).total
    const r4 = codes((await gateway.deals.list({ forecastKeys: ['won'] })).items)
    const r5 = codes((await gateway.deals.list({ forecastKeys: ['lost'] })).items)
    const r6 = (await gateway.deals.list({ statusKey: 'contract_completed' })).total
    const r7 = (await gateway.deals.list({ ownerId: USER_ID.old })).total
    // then: 조건에 맞는 Deal만 돌려준다
    expect(r1).toEqual(codesOf(1, 2, 7, 11, 13, 16, 20, 24))
    expect(r2).toEqual(codes(mine.items))
    expect(r3).toBe(7)
    expect(r4).toEqual(codesOf(11, 12, 24))
    expect(r5).toEqual(codesOf(16))
    expect(r6).toBe(3)
    expect(r7).toBe(1)
  })

  it('Forecast 조건은 여러 key 중 하나와 일치하는 Deal(OR)이다 (다중 조건)', async () => {
    // given: Won·Lost 각각의 결과
    const { gateway } = await mockAs('kim')
    const won = codes((await gateway.deals.list({ forecastKeys: ['won'] })).items)
    const lost = codes((await gateway.deals.list({ forecastKeys: ['lost'] })).items)
    const both = codes((await gateway.deals.list({ forecastKeys: ['won', 'lost'] })).items)
    // when: 여러 Forecast key로 검색한다
    const r1 = codes((await gateway.deals.list({ forecastKeys: ['lost', 'lost'] })).items)
    const r2 = (await gateway.deals.list({ forecastKeys: ['no_such'] })).total
    const r3 = codes((await gateway.deals.list({ forecastKeys: ['no_such', 'lost'] })).items)
    const r4 = (await gateway.deals.list({ forecastKeys: [] })).total
    // then: key 중 하나와 일치하는 Deal의 합집합이다
    expect(both).toEqual(expect.arrayContaining([...won, ...lost]))
    expect(both).toHaveLength(won.length + lost.length)
    expect(r1).toEqual(lost)
    expect(r2).toBe(0)
    expect(r3).toEqual(lost)
    expect(r4).toBe((await gateway.deals.list({})).total)
  })

  it('Vendor 필터는 id가 같은 Deal만, 없는 id는 0건이다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    // when: Vendor id로 검색한다
    const r1 = (await gateway.deals.list({ vendorId: seedVendorId('Silverfort') })).total
    const r2 = (await gateway.deals.list({ vendorId: NO_SUCH_ID })).total
    // then: id가 같은 Deal만 나오고 없는 id는 0건이다
    expect(r1).toBe(7)
    expect(r2).toBe(0)
  })

  it('Solution 필터는 대소문자 무시 부분 일치 텍스트이고 Vendor와 AND다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    const silverfort = seedVendorId('Silverfort')
    // when: Solution 텍스트로 검색한다
    const r1 = (await gateway.deals.list({ solution: 'itdr' })).total
    const r2 = (await gateway.deals.list({ solution: '  MF  ' })).total
    const r3 = (await gateway.deals.list({ vendorId: silverfort, solution: 'itdr' })).total
    const r4 = (await gateway.deals.list({ vendorId: seedVendorId('Okta'), solution: 'itdr' })).total
    const r5 = (await gateway.deals.list({ solution: '   ' })).total
    const r6 = (await gateway.deals.list({ solution: 'no-such-text' })).total
    // then: 대소문자 무시 부분 일치이고 Vendor 조건과 AND다
    expect(r1).toBe(4)
    expect(r2).toBe(3)
    expect(r3).toBe(4)
    expect(r4).toBe(0)
    expect(r5).toBe((await gateway.deals.list({})).total)
    expect(r6).toBe(0)
  })

  it('분기만 고르면 Fake 시계의 올해 그 분기이다(작년 같은 분기는 제외)', async () => {
    // given: Fake 시계 2026-10-15에 작년 4분기 Deal을 등록한 상태
    const { gateway } = await mockAs('kim') // Fake 시계 2026-10-15
    const created = await gateway.deals.create({
      ...dealInputFor('2025-11-15'),
    })
    // when: 연도 없이 4분기만 고른다
    const quarterOnly = (await gateway.deals.list({ quarters: [4], limit: 100 })).items
    const thisYear = (await gateway.deals.list({ year: 2026, quarters: [4], limit: 100 })).items

    // then: 올해 4분기와 같고 작년 Deal은 제외된다
    expect(quarterOnly.map((d) => d.code).sort()).toEqual(thisYear.map((d) => d.code).sort())
    expect(quarterOnly.map((d) => d.code)).not.toContain(created.code)
    const lastYear = (await gateway.deals.list({ year: 2025, quarters: [4], limit: 100 })).items
    expect(lastYear.map((d) => d.code)).toContain(created.code)
  })

  it('연도·분기 필터는 Expected Close 기준이고 경계를 포함한다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    // when: 연도·분기로 검색한다
    const all = (await gateway.deals.list({ limit: 100 })).items
    const q4 = (await gateway.deals.list({ year: 2026, quarters: [4], limit: 100 })).items
    expect(q4.length).toBeGreaterThan(0)
    // then: Expected Close 기준이고 분기별 합이 연도 전체와 같다
    for (const d of q4) expect(d.revenueDate >= '2026-10-01' && d.revenueDate <= '2026-12-31').toBe(true)
    const byYear = (await gateway.deals.list({ year: 2026, limit: 100 })).items
    let sum = 0
    for (const quarter of [1, 2, 3, 4] as const) {
      sum += (await gateway.deals.list({ year: 2026, quarters: [quarter], limit: 100 })).total
    }
    expect(sum).toBe(byYear.length)
    expect(all.length).toBeGreaterThan(byYear.length)
  })

  it('P6 월 필터는 그 달 1일~말일(양끝 포함)의 Deal만 돌려준다', async () => {
    // given: 2028년 2월 1일·29일과 인접 날짜의 Deal 4건
    const { gateway } = await mockAs('kim')
    const first = await gateway.deals.create({ ...dealInputFor('2028-02-01') })
    const last = await gateway.deals.create({ ...dealInputFor('2028-02-29') })
    await gateway.deals.create({ ...dealInputFor('2028-01-31') })
    await gateway.deals.create({ ...dealInputFor('2028-03-01') })
    // when: 2028년 2월로 검색한다
    const found = await gateway.deals.list({ year: 2028, month: 2, limit: 100 })
    const result = found.items.map((d) => d.code).sort()
    // then: 그 달 1일~말일(양끝 포함)의 Deal 2건만 나온다
    expect(result).toEqual([first.code, last.code].sort())
    expect(found.total).toBe(2)
  })

  it('P6 월만 고르면 Fake 시계의 올해 그 달이다', async () => {
    // given: Fake 시계 2026-10-15에 올해 3월과 작년 3월 Deal
    const { gateway } = await mockAs('kim') // Fake 시계 2026-10-15
    const mine = await gateway.deals.create({ ...dealInputFor('2026-03-15') })
    const lastYear = await gateway.deals.create({ ...dealInputFor('2025-03-15') })
    // when: 연도 없이 3월만 고른다
    const found = (await gateway.deals.list({ month: 3, limit: 100 })).items.map((d) => d.code)
    // then: 올해 3월 Deal만 나온다
    expect(found).toContain(mine.code)
    expect(found).not.toContain(lastYear.code)
  })

  it('P6 분기와 월을 함께 주면 422다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    // when·then: 분기와 월을 함께 주고 검색한다 → 422와 서버 문구다
    await expectApiError(gateway.deals.list({ year: 2026, quarters: [1], month: 1 }), 422, 'Quarter와 월은 함께 선택할 수 없습니다.')
  })

  it('P6 서버 한도: limit이 200을 넘으면 422이고 200은 허용된다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    // when: limit 201과 200으로 검색한다
    await expectApiError(gateway.deals.list({ limit: 201 }), 422)
    const result = (await gateway.deals.list({ limit: 200 })).limit
    // then: 201은 422이고 200은 허용된다
    expect(result).toBe(200)
  })

  it('최종 업데이트 기간은 lastUpdatedOn의 날짜가 양끝 포함 범위 안인 Deal만 돌려준다', async () => {
    // given: 최종 업데이트 날짜가 여러 날로 갈리는 시드 Deal
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const days = [...new Set(all.map((d) => d.lastUpdatedOn.slice(0, 10)))].sort()
    expect(days.length).toBeGreaterThan(2) // 시드가 날짜를 가르는 기준이 되어야 한다
    const [first, middle, last] = [days[0]!, days[Math.floor(days.length / 2)]!, days[days.length - 1]!]
    const dayOf = (d: { lastUpdatedOn: string }) => d.lastUpdatedOn.slice(0, 10)

    // when: 기준 날짜 하나·시작만·끝만·전체 기간으로 검색한다
    const exact = await gateway.deals.list({ updatedFrom: middle, updatedTo: middle, limit: 100 })
    const since = await gateway.deals.list({ updatedFrom: middle, limit: 100 })
    const until = await gateway.deals.list({ updatedTo: middle, limit: 100 })
    const everything = await gateway.deals.list({ updatedFrom: first, updatedTo: last, limit: 100 })

    // then: 날짜가 양끝 포함 범위 안인 Deal만 나온다
    expect(codes(exact.items)).toEqual(codes(all.filter((d) => dayOf(d) === middle)))
    expect(exact.total).toBeGreaterThan(0)
    expect(codes(since.items)).toEqual(codes(all.filter((d) => dayOf(d) >= middle)))
    expect(codes(until.items)).toEqual(codes(all.filter((d) => dayOf(d) <= middle)))
    expect(since.total).toBeLessThan(all.length)
    expect(until.total).toBeLessThan(all.length)
    expect(everything.total).toBe(all.length)
  })

  it('최종 업데이트 기간의 시작이 끝보다 늦으면 422로 거절한다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    // when·then: 시작이 끝보다 늦은 기간으로 검색한다 → 422로 거절한다
    await expectApiError(gateway.deals.list({ updatedFrom: '2026-07-01', updatedTo: '2026-06-30' }), 422)
  })

  it('최종 업데이트 기간은 연도·분기와 AND로 결합한다', async () => {
    // given: 4분기 Deal 중 하나의 최종 업데이트 날짜
    const { gateway } = await mockAs('kim')
    const q4 = (await gateway.deals.list({ year: 2026, quarters: [4], limit: 100 })).items
    const day = q4[0]!.lastUpdatedOn.slice(0, 10)
    // when: 연도·분기와 같은 날짜 기간을 함께 준다
    const both = await gateway.deals.list({ year: 2026, quarters: [4], updatedFrom: day, updatedTo: day, limit: 100 })
    const result = codes(both.items)
    // then: 두 조건을 AND로 결합한 결과다
    expect(result).toEqual(codes(q4.filter((d) => d.lastUpdatedOn.slice(0, 10) === day)))
  })

  it('정렬: 금액 내림차순, 이름 오름차순, Status 순서', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    // when: 금액·이름·Status로 정렬한다
    const byAmount = await gateway.deals.list({ sort: 'revenueAmount', order: 'desc' })
    // then: 금액 내림차순, 이름 오름차순, Status 순서대로 나온다
    expect(byAmount.items[0]?.code).toBe(dealCode(1))
    expect(byAmount.items[1]?.code).toBe(dealCode(10))
    const asc = (await gateway.deals.list({ sort: 'revenueAmount', order: 'asc' })).items
    expect(asc[0]?.code).toBe(dealCode(24))
    const names = (await gateway.deals.list({ sort: 'name', order: 'asc', limit: 100 })).items.map((d) => d.name)
    // 서버 규칙(DL-R13): 소문자로 바꾼 코드 포인트 순이다(로케일 순서가 아니다).
    const byCodePoint = (a: string, b: string) => (a.toLowerCase() < b.toLowerCase() ? -1 : a.toLowerCase() > b.toLowerCase() ? 1 : 0)
    expect(names).toEqual([...names].sort(byCodePoint))
    const status = (await gateway.deals.list({ sort: 'statusKey', order: 'asc', limit: 100 })).items
    expect(status[0]?.statusKey).toBe('prospecting')
    expect(status[status.length - 1]?.statusKey).toBe('contract_completed')
  })

  it('BANT Label 목록 필터는 없다: bantLabelIds를 줘도 조건이 되지 않는다', async () => {
    // given: BANT Budget이 선택된 Deal
    const { gateway } = await mockAs('kim')
    const d1 = await gateway.deals.get(dealCode(1))
    const budget = d1.bant.budget
    if (!budget) throw new Error('Deal 1은 Budget을 선택해야 한다')
    const all = await gateway.deals.list({ limit: 100 })
    // when: 옛 bantLabelIds 조건을 주고 검색한다
    const withOldKey = await gateway.deals.list({ limit: 100, bantLabelIds: { budget } } as never)
    // then: 조건이 되지 않아 전체 건수와 같다
    expect(withOldKey.total).toBe(all.total)
  })

  it('overdue는 risk가 overdue·overdue_stale인 Deal만, stale은 stale·overdue_stale인 Deal만 돌려주고 total이 맞다', async () => {
    // given: 위험 상태가 섞인 시드 Deal
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const overdue = all.filter((d) => d.risk === 'overdue' || d.risk === 'overdue_stale')
    const stale = all.filter((d) => d.risk === 'stale' || d.risk === 'overdue_stale')
    expect(overdue.length).toBeGreaterThan(0)
    expect(overdue.length).toBeLessThan(all.length)
    expect(stale.length).toBeGreaterThan(0)
    expect(stale.length).toBeLessThan(all.length)

    // when: overdue와 stale 필터를 각각 켜고 검색한다
    const foundOverdue = await gateway.deals.list({ overdue: true, limit: 100 })
    const foundStale = await gateway.deals.list({ stale: true, limit: 100 })

    // then: 해당 risk의 Deal만 나오고 total이 맞다
    expect(codes(foundOverdue.items)).toEqual(codes(overdue))
    expect(foundOverdue.total).toBe(overdue.length)
    expect(codes(foundStale.items)).toEqual(codes(stale))
    expect(foundStale.total).toBe(stale.length)
  })

  it('둘 다 켜면 어느 하나라도 해당하는 Deal이고 Won·Lost는 어느 쪽에도 걸리지 않는다', async () => {
    // given: 위험 상태가 섞인 시드 Deal
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const either = all.filter((d) => d.risk !== null)

    // when: overdue와 stale을 함께 켜고 검색한다
    const found = await gateway.deals.list({ overdue: true, stale: true, limit: 100 })

    // then: 위험이 있는 Deal만 나오고 Won·Lost는 걸리지 않는다
    expect(codes(found.items)).toEqual(codes(either))
    expect(found.total).toBe(either.length)
    for (const d of found.items) expect(['won', 'lost']).not.toContain(d.forecastKey)
  })

  it('위험 필터는 다른 조건과 AND이다', async () => {
    // given: 위험 상태가 섞인 시드 Deal
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 100 })).items
    const risky = all.filter((d) => d.risk !== null)
    const mineRisky = risky.filter((d) => d.ownerId === USER_ID.kim)
    expect(mineRisky.length).toBeGreaterThan(0)
    expect(mineRisky.length).toBeLessThan(risky.length)

    // when: 내 딜과 위험 필터를 함께 켜고 검색한다
    const found = await gateway.deals.list({ mine: true, overdue: true, stale: true, limit: 100 })

    // then: 내 딜 중 위험한 Deal만 나온다
    expect(codes(found.items)).toEqual(codes(mineRisky))
    expect(found.total).toBe(mineRisky.length)
  })

  it('total은 페이지와 무관하게 필터 결과 전체를 센다', async () => {
    // given: 위험한 Deal이 둘 이상인 시드
    const { gateway } = await mockAs('kim')
    const risky = (await gateway.deals.list({ limit: 100 })).items.filter((d) => d.risk !== null)
    expect(risky.length).toBeGreaterThan(1)

    // when: limit 1로 위험 필터 검색한다
    const page = await gateway.deals.list({ overdue: true, stale: true, limit: 1 })

    // then: items는 1건이고 total은 전체 위험 건수다
    expect(page.items).toHaveLength(1)
    expect(page.total).toBe(risky.length)
  })

  it('위험 필터를 끄면 아무 조건도 아니다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    const all = await gateway.deals.list({ limit: 100 })
    // when: 위험 필터를 모두 끄고 검색한다
    const off = await gateway.deals.list({ overdue: false, stale: false, limit: 100 })
    // then: 전체와 같은 건수다
    expect(off.total).toBe(all.total)
  })

  it('새 정렬: 담당자·고객사·파트너사·Vendor는 소문자 기준 오름차순·내림차순이고 동률은 code 오름차순이다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    const key: Record<'owner' | 'customer' | 'partner' | 'vendor', (d: DealRow) => string> = {
      owner: (d) => d.owner.name,
      customer: (d) => d.customer.company,
      partner: (d) => d.activePartner?.company ?? '',
      vendor: (d) => d.vendor?.name ?? '',
    }
    for (const sort of ['owner', 'customer', 'partner', 'vendor'] as const) {
      for (const order of ['asc', 'desc'] as const) {
        // when: 담당자·고객사·파트너사·Vendor를 오름·내림차순으로 정렬한다
        const rows = (await gateway.deals.list({ sort, order, limit: 100 })).items
        // then: 소문자 기준 순서이고 동률은 code 오름차순이다
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

  it('파트너나 Vendor가 없는 Deal은 오름차순·내림차순 모두 맨 뒤다', async () => {
    // given: 파트너 없는 Deal과 Vendor 없는 Deal
    const { gateway } = await mockAs('kim')
    const rows = (await gateway.deals.list({ limit: 100 })).items
    expect(rows.some((d) => d.activePartner === null)).toBe(true)
    const noVendor = await gateway.deals.create(dealInput(USER_ID.kim, { name: '벤더 없는 Deal', vendorId: null }))
    expect(noVendor.vendor).toBeNull()

    for (const order of ['asc', 'desc'] as const) {
      // when: 파트너로 정렬한다
      const byPartner = (await gateway.deals.list({ sort: 'partner', order, limit: 100 })).items
      // then: 파트너 없는 Deal은 두 방향 모두 맨 뒤다
      const firstAbsent = byPartner.findIndex((d) => d.activePartner === null)
      expect(byPartner.slice(firstAbsent).every((d) => d.activePartner === null)).toBe(true)
      expect(byPartner.slice(0, firstAbsent).every((d) => d.activePartner !== null)).toBe(true)
      // when: Vendor로 정렬한다
      const byVendor = (await gateway.deals.list({ sort: 'vendor', order, limit: 100 })).items
      // then: Vendor 없는 Deal은 두 방향 모두 맨 뒤다
      const firstNoVendor = byVendor.findIndex((d) => d.vendor === null)
      expect(firstNoVendor).toBeGreaterThanOrEqual(0)
      expect(byVendor.slice(firstNoVendor).every((d) => d.vendor === null)).toBe(true)
      expect(byVendor.slice(0, firstNoVendor).every((d) => d.vendor !== null)).toBe(true)
    }
  })

  it('Forecast 정렬은 Forecast 코드의 현재 순서다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    const order = (await gateway.codes.all()).forecasts.map((c) => c.key)
    for (const dir of ['asc', 'desc'] as const) {
      // when: Forecast로 정렬한다
      const rows = (await gateway.deals.list({ sort: 'forecastKey', order: dir, limit: 100 })).items
      // then: Forecast 코드의 현재 순서다
      const positions = rows.map((d) => order.indexOf(d.forecastKey))
      expect(positions).toEqual([...positions].sort((a, b) => (dir === 'asc' ? a - b : b - a)))
    }
  })

  it('정렬은 페이지 전체에 적용된다: 2페이지는 1페이지 다음 순서다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    const whole = (await gateway.deals.list({ sort: 'owner', order: 'asc', limit: 100 })).items.map((d) => d.code)
    const first = (await gateway.deals.list({ sort: 'owner', order: 'asc', offset: 0, limit: 10 })).items.map((d) => d.code)
    // when: 담당자 정렬로 1·2페이지를 읽는다
    const second = (await gateway.deals.list({ sort: 'owner', order: 'asc', offset: 10, limit: 10 })).items.map((d) => d.code)
    // then: 2페이지가 1페이지 다음 순서다
    expect([...first, ...second]).toEqual(whole.slice(0, 20))
  })

  it('행에는 파생값이 채워진다(고객·활성 파트너·Next Action·퇴사자 Owner)', async () => {
    // given: han 로그인
    const { gateway } = await mockAs('han')
    const rows = (await gateway.deals.list({ limit: 100 })).items
    const d1 = rows.find((d) => d.code === dealCode(1))
    // when: Deal 목록을 읽는다
    const r1 = rows.find((d) => d.code === dealCode(5))?.activePartner
    const r2 = rows.find((d) => d.code === dealCode(4))?.lastUpdatedOn.slice(0, 10)
    const r3 = rows.find((d) => d.code === dealCode(23))?.owner.status
    // then: 고객·활성 파트너·Next Action·퇴사자 Owner가 채워진다
    expect(d1).toMatchObject({
      customer: { company: '한빛은행', name: '정민수' },
      activePartner: { company: '에이원시스템', name: '표성호' },
      nextAction: { text: '계약서 초안 검토', dueDate: '2026-10-18', status: 'open' },
      owner: { name: '김영업' },
    })
    expect(r1).toBeNull()
    expect(r2).toBe('2026-09-24')
    expect(r3).toBe('resigned')
  })

  it('반환 객체를 바꿔도 저장소는 영향받지 않는다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')
    const row = (await gateway.deals.list({})).items[0]
    if (!row) throw new Error('empty')
    row.name = '변조'
    row.customer.company = '변조'
    // when: 반환된 행을 변조한 뒤 다시 읽는다
    const again = await gateway.deals.get(row.code)
    // then: 저장소 값은 그대로다
    expect(again.name).not.toBe('변조')
    expect(again.customer.company).not.toBe('변조')
  })
})

describe('deals.get / impact', () => {
  // 없는 code의 상세·삭제 영향은 404다.
  // 테스트 코드: DD-117
  it('없는 code는 404', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')

    // when·then: 없는 code로 상세와 삭제 영향을 읽는다 → 서버 문구의 404다
    await expectApiError(gateway.deals.get('20000101-ZZZZ'), 404, 'Deal을 찾을 수 없습니다.')
    await expectApiError(gateway.deals.impact('20000101-ZZZZ'), 404)
  })

  // 삭제 영향 건수는 이력·Action 목록 건수와 같다.
  // 테스트 코드: DD-117
  it('impact는 연쇄 삭제 건수와 목록 건수가 같다', async () => {
    // given: 이력·Action·첨부 3개가 있는 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    // when: 삭제 영향을 읽는다
    const impact = await gateway.deals.impact(code)
    // then: 이력·Action 건수가 목록 건수와 같고 첨부는 3이다
    expect(impact.historyCount).toBe((await gateway.history.list(code, {})).length)
    expect(impact.actionCount).toBe((await gateway.actions.list(code, {})).length)
    expect(impact.attachmentCount).toBe(3)
  })
})

describe('deals.list의 서버 검증 정렬 (DL 목록 Fake가 서버 422를 따르는지)', () => {
  // 서버 DealSearchParams·DealQuery 규칙: 범위 밖 값은 422 request-validation 문구, NUL은 invalid-value 문구
  it.each([
    ['키워드 101자', { keyword: 'a'.repeat(101) }],
    ['Solution 트림 후 201자', { solution: ` ${'s'.repeat(201)} ` }],
    ['Status key 51자', { statusKey: 'k'.repeat(51) }],
    ['Forecast key 51자', { forecastKeys: ['k'.repeat(51)] }],
    ['Forecast key 101개', { forecastKeys: Array.from({ length: 101 }, (_, n) => `k${n}`) }],
    ['연도 1899', { year: 1899 }],
    ['월 13', { month: 13 }],
    ['offset -1', { offset: -1 }],
    ['limit 0', { limit: 0 }],
    ['limit 201', { limit: 201 }],
  ])('%s는 422다', async (_label, query) => {
    // given: 로그인한 sales
    const { gateway } = await mockAs('kim')
    // when·then: 범위 밖 조건으로 조회하면 422
    await expectApiError(gateway.deals.list(query), 422)
  })

  it('키워드·Solution의 NUL은 서버 문구의 422다', async () => {
    // given: 로그인한 sales
    const { gateway } = await mockAs('kim')
    // when·then: NUL이 든 값은 NUL 문구로 거절된다
    await expect(gateway.deals.list({ keyword: 'a\u0000b' })).rejects.toMatchObject({ message: '검색어에는 NUL 문자를 쓸 수 없습니다' })
    await expect(gateway.deals.list({ solution: 'a\u0000b' })).rejects.toMatchObject({ message: 'Solution에는 NUL 문자를 쓸 수 없습니다' })
  })

  it('최종 업데이트 날짜가 1900-01-01~2999-12-31 밖이면 서버 문구의 422다', async () => {
    // given: 로그인한 sales
    const { gateway } = await mockAs('kim')
    // when·then: 범위 밖 날짜는 서버 문구로 거절되고 양끝 날짜는 된다
    await expect(gateway.deals.list({ updatedFrom: '1899-12-31' })).rejects.toMatchObject({
      message: 'updated_from은(는) 1900-01-01부터 2999-12-31 사이여야 합니다',
    })
    await expect(gateway.deals.list({ updatedFrom: '1900-01-01', updatedTo: '2999-12-31' })).resolves.toBeDefined()
  })

  it('경계 값(키워드 100자·limit 200·Forecast key 100개)은 통과한다', async () => {
    // given: 로그인한 sales
    const { gateway } = await mockAs('kim')
    // when: 한도 값으로 조회한다
    const byKeyword = await gateway.deals.list({ keyword: 'a'.repeat(100), limit: 200 })
    const byForecasts = await gateway.deals.list({ forecastKeys: Array.from({ length: 100 }, (_, n) => `k${n}`) })
    // then: 오류 없이 조회된다
    expect(byKeyword).toBeDefined()
    expect(byForecasts).toBeDefined()
  })
})
