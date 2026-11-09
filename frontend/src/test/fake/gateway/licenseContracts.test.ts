import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs } from '../testing'

/**
 * 계약관리 Fake: 시드와 서버 규칙(AC1~AC21 중 Fake가 흉내 내는 부분). 시드 요구사항
 * - 모든 Won 시드 Deal(Forecast won)에 계약이 최소 1건 있고, Won이 아닌 시드 Deal에는 없다
 * - 네 상태가 모두 있고 Vendor 4개 이상·담당영업 3명 이상이 섞여 있다
 * - 발급 상태 계약은 Deal당 최대 1건이다
 * - 서버 시계 2027-03-15 기준 발급 계약 중 30일 이내·60일 이내 만료가 모두 있다(만료 임박 색 확인용)
 * - 목록 기본 순서는 종료일 오름차순, 값 없는 종료일은 맨 뒤
 */
const QUERY = { sort: 'licenseEnd', order: 'asc' } as const
const isIssued = (status: string) => status === 'issued_new' || status === 'issued_renewal'

describe('license contracts Fake: seed', () => {
  // Won 시드 Deal마다 계약이 있고 그 밖의 Deal에는 없다(Deal의 계약 건수와 일치).
  it('has a contract for every Won seed deal and none for the others', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('root')
    const deals = await gateway.deals.list({ limit: 100 })
    // when: Deal 목록과 계약 목록을 읽는다
    const contracts = (await gateway.licenseContracts.list(QUERY, 0, 200)).items

    // then: Won Deal은 계약 1건 이상, 나머지는 0건이고 건수가 일치한다
    for (const deal of deals.items) {
      const mine = contracts.filter((c) => c.dealCode === deal.code)
      if (deal.forecastKey === 'won') expect(mine.length, deal.name).toBeGreaterThan(0)
      else expect(mine, deal.name).toHaveLength(0)
      expect(deal.licenseContractCount, deal.name).toBe(mine.length)
    }
  })

  // 네 상태와 Vendor 4개 이상, 담당영업 3명 이상이 섞여 있다.
  it('has all four statuses, at least four vendors and three owners', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('root')
    // when: 계약 목록을 읽는다
    const items = (await gateway.licenseContracts.list(QUERY, 0, 200)).items

    // then: 상태·Vendor·담당영업의 가짓수가 기준 이상이다
    expect(new Set(items.map((c) => c.status))).toEqual(new Set(['not_issued', 'issued_new', 'issued_renewal', 'ended']))
    expect(new Set(items.flatMap((c) => (c.vendor ? [c.vendor.name] : []))).size).toBeGreaterThanOrEqual(4)
    expect(new Set(items.map((c) => c.salesOwner.id)).size).toBeGreaterThanOrEqual(3)
  })

  // Deal당 발급 계약은 최대 1건이고 기간이 일관된다.
  // 테스트 코드: LC-042
  it('keeps one issued contract per deal and consistent periods', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('root')
    const items = (await gateway.licenseContracts.list(QUERY, 0, 200)).items

    const issuedByDeal = new Map<string, number>()
    // when: 계약 목록을 읽는다
    for (const c of items.filter((x) => isIssued(x.status))) issuedByDeal.set(c.dealCode, (issuedByDeal.get(c.dealCode) ?? 0) + 1)
    // then: Deal마다 발급 상태 계약이 1건 이하이고 종료일 계산이 맞다
    expect([...issuedByDeal.values()].every((n) => n === 1)).toBe(true)
    for (const c of items) {
      if (c.status === 'not_issued') expect([c.licenseStart, c.licenseEnd, c.term]).toEqual([null, null, null])
      else expect(c.licenseStart && c.licenseEnd && c.term).toBeTruthy()
    }
  })

  // 서버 시계 2027-03-15 기준 위험·주의 구간과 그 밖의 발급 계약이 모두 있다.
  // 테스트 코드: LC-027
  it('has issued contracts in both expiry bands and some outside them (today 2027-03-15)', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway, clock } = await mockAs('root', { now: '2027-03-15T10:00:00+09:00' })
    clock.setNow('2027-03-15T10:00:00+09:00')
    const issued = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.filter((c) => isIssued(c.status))
    // when: 계약 목록을 읽는다
    const plus = (months: number) => {
      const d = new Date('2027-03-15T00:00:00Z')
      d.setUTCMonth(d.getUTCMonth() + months)
      return d.toISOString().slice(0, 10)
    }

    // then: 위험·주의 구간 계약과 구간 밖 계약이 모두 있다
    expect(issued.some((c) => c.licenseEnd! < plus(1))).toBe(true)
    expect(issued.some((c) => c.licenseEnd! >= plus(1) && c.licenseEnd! < plus(2))).toBe(true)
    expect(issued.some((c) => c.licenseEnd! >= plus(2))).toBe(true)
    for (const status of ['issued_new', 'issued_renewal'] as const) {
      expect(issued.filter((c) => c.status === status).some((c) => c.licenseEnd! < plus(2)), status).toBe(true)
    }
  })

  // 기본 정렬은 종료일 오름차순이고 날짜 없는 계약이 맨 뒤다.
  // 테스트 코드: LC-016
  it('sorts by end date ascending by default with empty dates last', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('root')
    const ends = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.map((c) => c.licenseEnd)
    // when: 조건 없이 목록을 읽는다
    const dated = ends.filter((e): e is string => e !== null)

    // then: 종료일 오름차순에 종료일 없는 계약이 뒤다
    expect(ends.slice(0, dated.length)).toEqual([...dated].sort())
    expect(ends.slice(dated.length).every((e) => e === null)).toBe(true)
  })

  // 목록이 둘째 쪽을 필요로 하도록 계약이 50건보다 많다.
  // 테스트 코드: LC-023
  it('has more than fifty contracts so that the list needs a second page', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    // when: 계약 전체 건수를 센다
    const { gateway } = await mockAs('root')

    // then: 50건보다 많다
    expect((await gateway.licenseContracts.list(QUERY, 0, 50)).total).toBeGreaterThan(50)
  })
})

describe('license contracts Fake: rules', () => {
  // Won 진입 때 계약이 생기고 Won 이탈 때는 요청했을 때만 지워진다.
  // 테스트 코드: LC-003, LC-006, LC-007
  it('creates a contract when a deal enters Won and deletes it only when asked on leaving Won', async () => {
    // given: 계약이 없는 Won이 아닌 시드 Deal
    const { gateway } = await mockAs('kim')
    // when: Won으로 바꿨다가 삭제 값을 달리해 Won을 벗어난다
    const code = dealCode(2) // Won이 아닌 시드 Deal
    // then: 진입 때 계약 1건이 생기고, 삭제 true일 때만 계약이 사라진다
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(0)

    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 700_000_000, revenueDate: '2027-02-01' } })
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(1)
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } })
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(1)
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 700_000_000, revenueDate: '2027-02-01' } })
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' }, deleteLicenseContracts: true })

    expect((await gateway.deals.get(code)).licenseContractCount).toBe(0)
  })

  // Won으로 등록하거나 폼 수정·Action 등록으로 Won이 되어도 계약이 생긴다.
  // 테스트 코드: LC-001, LC-003
  it('creates the contract for a deal registered as Won, through update and through an action too', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when: Won으로 Deal을 등록하고, 폼 수정과 Action 등록으로도 Won으로 바꾼다
    await gateway.deals.update(code, { statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 700_000_000, revenueDate: '2027-02-01' })
    // then: 각 경로마다 계약이 1건 생긴다
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(1)
    await gateway.deals.update(code, { statusKey: 'technical_evaluation', forecastKey: 'commit', deleteLicenseContracts: true })
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(0)
    await gateway.actions.create(code, {
      type: { name: '미팅' },
      progress: '계약 체결',
      nextAction: '',
      dueDate: '',
      memo: '',
      statusChanges: [{ change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 700_000_000, revenueDate: '2027-02-01' } }],
    })
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(1)
  })

  // sales의 계약 삭제는 거절되고 user는 읽기만 할 수 있다.
  // 테스트 코드: LC-059
  it('refuses a delete by sales and lets a read-only user only read', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('kim')
    const [first] = (await gateway.licenseContracts.list(QUERY, 0, 1)).items
    await expectApiError(gateway.licenseContracts.remove(first!.id), 403, '계약 삭제는 관리자만 할 수 있습니다.')
    const reader = await mockAs('han')

    // when: sales가 삭제하고 user가 종료를 시도한다
    await expectApiError(reader.gateway.licenseContracts.end(first!.id), 403)
    // then: sales는 관리자만 문구의 403, user의 쓰기는 403이고 읽기는 된다
    expect((await reader.gateway.licenseContracts.get(first!.id)).id).toBe(first!.id)
  })

  // 없는 계약을 삭제하려 하면 admin이 아닌 요청자는 404가 아니라 403을 받는다.
  // 테스트 코드: LC-083, LC-029
  it('answers a delete of a missing contract with 403 unless the requester is an admin', async () => {
    // given: 존재하지 않는 계약 id와 sales·user·admin 요청자
    const missing = 987_654_321
    // when: 각자 그 계약을 삭제한다
    const sales = await mockAs('kim')
    const reader = await mockAs('han')
    const admin = await mockAs('root')
    // then: sales와 user는 403(404가 아님), admin만 404
    await expectApiError(sales.gateway.licenseContracts.remove(missing), 403, '계약 삭제는 관리자만 할 수 있습니다.')
    await expectApiError(reader.gateway.licenseContracts.remove(missing), 403)
    await expectApiError(admin.gateway.licenseContracts.remove(missing), 404, '라이선스 계약을 찾을 수 없습니다.')
  })

  // 삭제 영향이 Deal의 계약 건수를 담는다.
  // 테스트 코드: LC-079
  it('reports the contract count of a deal in the deletion impact', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('root')
    const issued = (await gateway.licenseContracts.list({ ...QUERY, status: 'issued_new' }, 0, 1)).items[0]!
    // when: Deal 삭제 영향을 읽는다
    const mine = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.filter((c) => c.dealCode === issued.dealCode)

    // then: 계약 건수가 계약 목록과 같다
    expect((await gateway.deals.impact(issued.dealCode)).licenseContractCount).toBe(mine.length)
  })
})

const WON_EXIT_BLOCKED =
  '발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요.'
const DEAL_NOT_WON = 'Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다.'
const LEAVE_WON = { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } } as const
const YEAR = { techOwner: '', inspection: 'none', note: '', start: '2027-01-01', term: { amount: 1, unit: 'year' } } as const

describe('license contracts Fake: issued contract rules (F)', () => {
  // 발급 상태 계약이 있는 Deal만 hasIssuedLicenseContract가 true다.
  // 테스트 코드: LC-030
  it('flags hasIssuedLicenseContract exactly for deals with an issued-state contract (seed)', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('root')
    const contracts = (await gateway.licenseContracts.list(QUERY, 0, 200)).items
    const deals = await gateway.deals.list({ limit: 100 })

    // when: Deal 목록을 읽는다
    for (const deal of deals.items) {
      const expected = contracts.some((c) => c.dealCode === deal.code && isIssued(c.status))
      expect(deal.hasIssuedLicenseContract, deal.name).toBe(expected)
      expect((await gateway.deals.get(deal.code)).hasIssuedLicenseContract, deal.name).toBe(expected)
    }
    // then: 발급 상태 계약이 있는 Deal만 true다
    expect(deals.items.find((d) => d.code === dealCode(11))?.hasIssuedLicenseContract).toBe(true)
    expect(deals.items.find((d) => d.code === dealCode(24))?.hasIssuedLicenseContract).toBe(true)
    expect(deals.items.find((d) => d.code === dealCode(12))?.hasIssuedLicenseContract).toBe(false)
  })

  // 시드 계약은 모두 Won Deal에 속해 dealIsWon이 true다.
  // 테스트 코드: LC-028
  it('sets dealIsWon true on every seed contract (all of them belong to Won deals)', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    // when: 계약 목록을 읽는다
    const { gateway } = await mockAs('root')

    // then: 모든 계약의 dealIsWon이 true다
    for (const c of (await gateway.licenseContracts.list(QUERY, 0, 200)).items) expect(c.dealIsWon, c.dealCode).toBe(true)
  })

  // 발급 계약이 있는 시드 Deal은 세 경로 모두 Won을 벗어날 수 없고 아무것도 바뀌지 않는다.
  // 테스트 코드: LC-008
  it.each([11, 24])('refuses to leave Won for seed deal %i, by change, update and action, and changes nothing', async (no) => {
    // given: 발급 계약이 있는 시드 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(no)
    const before = await gateway.deals.get(code)

    await expectApiError(gateway.deals.applyChange(code, { ...LEAVE_WON, deleteLicenseContracts: true }), 409, WON_EXIT_BLOCKED)
    await expectApiError(gateway.deals.applyChange(code, LEAVE_WON), 409, WON_EXIT_BLOCKED)
    await expectApiError(gateway.deals.update(code, { statusKey: 'technical_evaluation', forecastKey: 'commit', deleteLicenseContracts: false }), 409, WON_EXIT_BLOCKED)
    const actionsBefore = await gateway.actions.list(code, {})
    // when: 인라인 변경·폼 수정·Action 등록으로 Won을 벗어난다
    await expectApiError(
      gateway.actions.create(code, { type: { name: '미팅' }, progress: '해지 논의', nextAction: '', dueDate: '', memo: '', statusChanges: [LEAVE_WON], deleteLicenseContracts: true }),
      409,
      WON_EXIT_BLOCKED,
    )

    const after = await gateway.deals.get(code)
    // then: 409 문구, Deal과 계약은 그대로다
    expect([after.statusKey, after.forecastKey, after.licenseContractCount]).toEqual([before.statusKey, before.forecastKey, before.licenseContractCount])
    expect(await gateway.actions.list(code, {})).toHaveLength(actionsBefore.length)
  })

  // admin이 발급 계약을 지우면 그 Deal은 Won을 벗어날 수 있다.
  // 테스트 코드: LC-009
  it('lets the deal leave Won once an admin deleted its issued contract', async () => {
    // given: 발급 계약이 있는 Won 시드 Deal
    const { gateway } = await mockAs('root')
    const code = dealCode(24)
    const issued = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.find((c) => c.dealCode === code && isIssued(c.status))!
    await expectApiError(gateway.deals.applyChange(code, LEAVE_WON), 409, WON_EXIT_BLOCKED)

    await gateway.licenseContracts.remove(issued.id)
    // when: admin이 계약을 삭제한 뒤 Won을 벗어난다
    await gateway.deals.applyChange(code, { ...LEAVE_WON, deleteLicenseContracts: false })

    // then: 요청이 성공하고 Forecast가 바뀐다
    expect((await gateway.deals.get(code)).forecastKey).toBe('commit')
  })

  // Won을 유지하는 변경과 미발급 계약뿐인 Deal의 Won 이탈은 막지 않는다.
  // 테스트 코드: LC-004, LC-009
  it('does not block a change that starts and ends in Won, nor leaving Won with only a not-issued contract', async () => {
    // given: Fake 게이트웨이의 시드 데이터
    const { gateway } = await mockAs('kim')

    await gateway.deals.applyChange(dealCode(11), { change: { field: 'revenueAmount', value: 123_000_000 } })
    // when: Won 유지 변경과 미발급 계약 Deal의 Won 이탈을 한다
    await gateway.deals.applyChange(dealCode(12), { ...LEAVE_WON, deleteLicenseContracts: true })

    // then: 모두 성공한다
    expect((await gateway.deals.get(dealCode(11))).forecastKey).toBe('won')
    expect((await gateway.deals.get(dealCode(12))).licenseContractCount).toBe(0)
  })

  // Won이 아닌 Deal에서는 발급·갱신이 거절되고 칸 수정과 종료는 된다.
  // 테스트 코드: LC-043, LC-051
  it('rejects issue and renew when the deal is not Won, but allows edits and ending', async () => {
    // given: Won을 벗어난 Deal의 계약
    const { gateway } = await mockAs('kim')
    const code = dealCode(12)
    // when: 발급·갱신, 칸 수정, 종료를 요청한다
    const contract = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.find((c) => c.dealCode === code)!
    // then: 발급·갱신은 409 Won 문구, 수정·종료는 성공한다
    expect(contract.dealIsWon).toBe(true)
    await gateway.deals.applyChange(code, { ...LEAVE_WON, deleteLicenseContracts: false })

    expect((await gateway.licenseContracts.get(contract.id)).dealIsWon).toBe(false)
    await expectApiError(gateway.licenseContracts.issue(contract.id, YEAR), 409, DEAL_NOT_WON)
    await expectApiError(gateway.licenseContracts.renew(contract.id, YEAR), 409, DEAL_NOT_WON)
    expect((await gateway.licenseContracts.get(contract.id)).status).toBe('not_issued')
    expect((await gateway.licenseContracts.update(contract.id, { techOwner: '수정', inspection: 'yearly', note: '' })).techOwner).toBe('수정')
    expect((await gateway.licenseContracts.end(contract.id)).status).toBe('ended')
  })

  // 발급하면 Deal의 발급 여부가 켜지고 종료하면 꺼진다.
  // 테스트 코드: LC-030
  it('turns the flag on when a contract of a Won deal is issued and off when it ends', async () => {
    // given: Won Deal의 미발급 계약
    const { gateway } = await mockAs('kim')
    const code = dealCode(12)
    const contract = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.find((c) => c.dealCode === code)!

    // when: 발급하고 종료한다
    await gateway.licenseContracts.issue(contract.id, YEAR)
    // then: 발급 여부가 true였다가 false가 된다
    expect((await gateway.deals.get(code)).hasIssuedLicenseContract).toBe(true)
    await expectApiError(gateway.deals.applyChange(code, LEAVE_WON), 409, WON_EXIT_BLOCKED)
    await gateway.licenseContracts.end(contract.id)

    expect((await gateway.deals.get(code)).hasIssuedLicenseContract).toBe(false)
  })
})
