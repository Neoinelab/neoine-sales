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
  it('has a contract for every Won seed deal and none for the others', async () => {
    const { gateway } = await mockAs('root')
    const deals = await gateway.deals.list({ limit: 100 })
    const contracts = (await gateway.licenseContracts.list(QUERY, 0, 200)).items

    for (const deal of deals.items) {
      const mine = contracts.filter((c) => c.dealCode === deal.code)
      if (deal.forecastKey === 'won') expect(mine.length, deal.name).toBeGreaterThan(0)
      else expect(mine, deal.name).toHaveLength(0)
      expect(deal.licenseContractCount, deal.name).toBe(mine.length)
    }
  })

  it('has all four statuses, at least four vendors and three owners', async () => {
    const { gateway } = await mockAs('root')
    const items = (await gateway.licenseContracts.list(QUERY, 0, 200)).items

    expect(new Set(items.map((c) => c.status))).toEqual(new Set(['not_issued', 'issued_new', 'issued_renewal', 'ended']))
    expect(new Set(items.flatMap((c) => (c.vendor ? [c.vendor.name] : []))).size).toBeGreaterThanOrEqual(4)
    expect(new Set(items.map((c) => c.salesOwner.id)).size).toBeGreaterThanOrEqual(3)
  })

  it('keeps one issued contract per deal and consistent periods', async () => {
    const { gateway } = await mockAs('root')
    const items = (await gateway.licenseContracts.list(QUERY, 0, 200)).items

    const issuedByDeal = new Map<string, number>()
    for (const c of items.filter((x) => isIssued(x.status))) issuedByDeal.set(c.dealCode, (issuedByDeal.get(c.dealCode) ?? 0) + 1)
    expect([...issuedByDeal.values()].every((n) => n === 1)).toBe(true)
    for (const c of items) {
      if (c.status === 'not_issued') expect([c.licenseStart, c.licenseEnd, c.term]).toEqual([null, null, null])
      else expect(c.licenseStart && c.licenseEnd && c.term).toBeTruthy()
    }
  })

  it('has issued contracts in both expiry bands and some outside them (today 2027-03-15)', async () => {
    const { gateway, clock } = await mockAs('root', { now: '2027-03-15T10:00:00+09:00' })
    clock.setNow('2027-03-15T10:00:00+09:00')
    const issued = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.filter((c) => isIssued(c.status))
    const plus = (months: number) => {
      const d = new Date('2027-03-15T00:00:00Z')
      d.setUTCMonth(d.getUTCMonth() + months)
      return d.toISOString().slice(0, 10)
    }

    expect(issued.some((c) => c.licenseEnd! < plus(1))).toBe(true)
    expect(issued.some((c) => c.licenseEnd! >= plus(1) && c.licenseEnd! < plus(2))).toBe(true)
    expect(issued.some((c) => c.licenseEnd! >= plus(2))).toBe(true)
    for (const status of ['issued_new', 'issued_renewal'] as const) {
      expect(issued.filter((c) => c.status === status).some((c) => c.licenseEnd! < plus(2)), status).toBe(true)
    }
  })

  it('sorts by end date ascending by default with empty dates last', async () => {
    const { gateway } = await mockAs('root')
    const ends = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.map((c) => c.licenseEnd)
    const dated = ends.filter((e): e is string => e !== null)

    expect(ends.slice(0, dated.length)).toEqual([...dated].sort())
    expect(ends.slice(dated.length).every((e) => e === null)).toBe(true)
  })

  it('has more than fifty contracts so that the list needs a second page', async () => {
    const { gateway } = await mockAs('root')

    expect((await gateway.licenseContracts.list(QUERY, 0, 50)).total).toBeGreaterThan(50)
  })
})

describe('license contracts Fake: rules', () => {
  it('creates a contract when a deal enters Won and deletes it only when asked on leaving Won', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2) // Won이 아닌 시드 Deal
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(0)

    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 700_000_000, revenueDate: '2027-02-01' } })
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(1)
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } })
    expect((await gateway.deals.get(code)).licenseContractCount).toBe(1)
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'won' }, resolution: { revenueAmount: 700_000_000, revenueDate: '2027-02-01' } })
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' }, deleteLicenseContracts: true })

    expect((await gateway.deals.get(code)).licenseContractCount).toBe(0)
  })

  it('creates the contract for a deal registered as Won, through update and through an action too', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    await gateway.deals.update(code, { statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 700_000_000, revenueDate: '2027-02-01' })
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

  it('refuses a delete by sales and lets a read-only user only read', async () => {
    const { gateway } = await mockAs('kim')
    const [first] = (await gateway.licenseContracts.list(QUERY, 0, 1)).items
    await expectApiError(gateway.licenseContracts.remove(first!.id), 403, '계약 삭제는 관리자만 할 수 있습니다.')
    const reader = await mockAs('han')

    await expectApiError(reader.gateway.licenseContracts.end(first!.id), 403)
    expect((await reader.gateway.licenseContracts.get(first!.id)).id).toBe(first!.id)
  })

  it('reports the contract count of a deal in the deletion impact', async () => {
    const { gateway } = await mockAs('root')
    const issued = (await gateway.licenseContracts.list({ ...QUERY, status: 'issued_new' }, 0, 1)).items[0]!
    const mine = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.filter((c) => c.dealCode === issued.dealCode)

    expect((await gateway.deals.impact(issued.dealCode)).licenseContractCount).toBe(mine.length)
  })
})

const WON_EXIT_BLOCKED =
  '발급된 라이선스 계약이 있는 Deal은 Won에서 다른 상태로 바꿀 수 없습니다. 계약 정보가 잘못되었다면 관리자에게 계약 삭제를 요청하세요.'
const DEAL_NOT_WON = 'Won인 Deal의 계약만 발급하거나 갱신할 수 있습니다.'
const LEAVE_WON = { change: { field: 'forecastKey', value: 'commit' }, resolution: { statusKey: 'technical_evaluation' } } as const
const YEAR = { techOwner: '', inspection: 'none', note: '', start: '2027-01-01', term: { amount: 1, unit: 'year' } } as const

describe('license contracts Fake: issued contract rules (F)', () => {
  it('flags hasIssuedLicenseContract exactly for deals with an issued-state contract (seed)', async () => {
    const { gateway } = await mockAs('root')
    const contracts = (await gateway.licenseContracts.list(QUERY, 0, 200)).items
    const deals = await gateway.deals.list({ limit: 100 })

    for (const deal of deals.items) {
      const expected = contracts.some((c) => c.dealCode === deal.code && isIssued(c.status))
      expect(deal.hasIssuedLicenseContract, deal.name).toBe(expected)
      expect((await gateway.deals.get(deal.code)).hasIssuedLicenseContract, deal.name).toBe(expected)
    }
    expect(deals.items.find((d) => d.code === dealCode(11))?.hasIssuedLicenseContract).toBe(true)
    expect(deals.items.find((d) => d.code === dealCode(24))?.hasIssuedLicenseContract).toBe(true)
    expect(deals.items.find((d) => d.code === dealCode(12))?.hasIssuedLicenseContract).toBe(false)
  })

  it('sets dealIsWon true on every seed contract (all of them belong to Won deals)', async () => {
    const { gateway } = await mockAs('root')

    for (const c of (await gateway.licenseContracts.list(QUERY, 0, 200)).items) expect(c.dealIsWon, c.dealCode).toBe(true)
  })

  it.each([11, 24])('refuses to leave Won for seed deal %i, by change, update and action, and changes nothing', async (no) => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(no)
    const before = await gateway.deals.get(code)

    await expectApiError(gateway.deals.applyChange(code, { ...LEAVE_WON, deleteLicenseContracts: true }), 409, WON_EXIT_BLOCKED)
    await expectApiError(gateway.deals.applyChange(code, LEAVE_WON), 409, WON_EXIT_BLOCKED)
    await expectApiError(gateway.deals.update(code, { statusKey: 'technical_evaluation', forecastKey: 'commit', deleteLicenseContracts: false }), 409, WON_EXIT_BLOCKED)
    const actionsBefore = await gateway.actions.list(code, {})
    await expectApiError(
      gateway.actions.create(code, { type: { name: '미팅' }, progress: '해지 논의', nextAction: '', dueDate: '', memo: '', statusChanges: [LEAVE_WON], deleteLicenseContracts: true }),
      409,
      WON_EXIT_BLOCKED,
    )

    const after = await gateway.deals.get(code)
    expect([after.statusKey, after.forecastKey, after.licenseContractCount]).toEqual([before.statusKey, before.forecastKey, before.licenseContractCount])
    expect(await gateway.actions.list(code, {})).toHaveLength(actionsBefore.length)
  })

  it('lets the deal leave Won once an admin deleted its issued contract', async () => {
    const { gateway } = await mockAs('root')
    const code = dealCode(24)
    const issued = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.find((c) => c.dealCode === code && isIssued(c.status))!
    await expectApiError(gateway.deals.applyChange(code, LEAVE_WON), 409, WON_EXIT_BLOCKED)

    await gateway.licenseContracts.remove(issued.id)
    await gateway.deals.applyChange(code, { ...LEAVE_WON, deleteLicenseContracts: false })

    expect((await gateway.deals.get(code)).forecastKey).toBe('commit')
  })

  it('does not block a change that starts and ends in Won, nor leaving Won with only a not-issued contract', async () => {
    const { gateway } = await mockAs('kim')

    await gateway.deals.applyChange(dealCode(11), { change: { field: 'revenueAmount', value: 123_000_000 } })
    await gateway.deals.applyChange(dealCode(12), { ...LEAVE_WON, deleteLicenseContracts: true })

    expect((await gateway.deals.get(dealCode(11))).forecastKey).toBe('won')
    expect((await gateway.deals.get(dealCode(12))).licenseContractCount).toBe(0)
  })

  it('rejects issue and renew when the deal is not Won, but allows edits and ending', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(12)
    const contract = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.find((c) => c.dealCode === code)!
    expect(contract.dealIsWon).toBe(true)
    await gateway.deals.applyChange(code, { ...LEAVE_WON, deleteLicenseContracts: false })

    expect((await gateway.licenseContracts.get(contract.id)).dealIsWon).toBe(false)
    await expectApiError(gateway.licenseContracts.issue(contract.id, YEAR), 409, DEAL_NOT_WON)
    await expectApiError(gateway.licenseContracts.renew(contract.id, YEAR), 409, DEAL_NOT_WON)
    expect((await gateway.licenseContracts.get(contract.id)).status).toBe('not_issued')
    expect((await gateway.licenseContracts.update(contract.id, { techOwner: '수정', inspection: 'yearly', note: '' })).techOwner).toBe('수정')
    expect((await gateway.licenseContracts.end(contract.id)).status).toBe('ended')
  })

  it('turns the flag on when a contract of a Won deal is issued and off when it ends', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(12)
    const contract = (await gateway.licenseContracts.list(QUERY, 0, 200)).items.find((c) => c.dealCode === code)!

    await gateway.licenseContracts.issue(contract.id, YEAR)
    expect((await gateway.deals.get(code)).hasIssuedLicenseContract).toBe(true)
    await expectApiError(gateway.deals.applyChange(code, LEAVE_WON), 409, WON_EXIT_BLOCKED)
    await gateway.licenseContracts.end(contract.id)

    expect((await gateway.deals.get(code)).hasIssuedLicenseContract).toBe(false)
  })
})
