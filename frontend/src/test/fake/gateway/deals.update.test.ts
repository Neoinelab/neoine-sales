import { describe, expect, it } from 'vitest'
import type { HistoryCategory } from '../../../shared/model/types'
import { seedSolutionId, seedVendorId } from '../../fixtures/vendors'
import { contactIdOf, dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'

async function categories(gw: Awaited<ReturnType<typeof mockAs>>['gateway'], code: string, since: number) {
  const all = await gw.history.list(code, {})
  return all.slice(0, all.length - since).map((h) => h.category)
}

describe('deals.update', () => {
  it('T-GW user는 403, 없는 code는 404', async () => {
    const han = await mockAs('han')
    await expectApiError(han.gateway.deals.update(dealCode(1), { name: 'x' }), 403)
    const kim = await mockAs('kim')
    await expectApiError(kim.gateway.deals.update('20000101-ZZZZ', { name: 'x' }), 404)
  })

  it('변경이 없으면 History도 updatedAt도 바뀌지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = await gateway.deals.get(code)
    const historyBefore = (await gateway.history.list(code, {})).length
    await gateway.deals.update(code, { name: before.name, revenueAmount: before.revenueAmount })
    expect((await gateway.history.list(code, {})).length).toBe(historyBefore)
    expect((await gateway.deals.get(code)).updatedAt).toBe(before.updatedAt)
  })

  it('R02 필드마다 History가 남는다(Owner/금액/Expected Close/Label/견적/POC/기타)', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length
    const labels = await gateway.labels.list()
    const budget = labels.find((l) => l.category === 'budget')
    if (!budget) throw new Error('label')
    const updated = await gateway.deals.update(code, {
      name: '대한제조 MFA 확대(수정)',
      ownerId: 'u-park',
      revenueAmount: 777_000_000,
      revenueDate: '2026-12-31',
      vendorId: seedVendorId('Okta'),
      solutionId: seedSolutionId('Okta', 'SSO'),
      users: 250,
      bant: { budget: { id: budget.id }, authority: null, need: null, timeline: null },
      quote: { submitted: 'YES', submittedDate: '2026-10-10' },
      poc: { state: 'ING', completedDate: null },
      procurement: '연말 일괄 구매',
    })
    expect(updated).toMatchObject({ name: '대한제조 MFA 확대(수정)', owner: { id: 'u-park' }, revenueAmount: 777_000_000, updatedAt: TEST_NOW })
    const cats = await categories(gateway, code, base)
    const expected: HistoryCategory[] = ['owner', 'amount', 'expectedClose', 'bant', 'other']
    for (const c of expected) expect(cats).toContain(c)
    expect(cats.filter((c) => c === 'other').length).toBe(7) // 이름, Vendor, Solution, Users, 견적, POC, 구매절차
    const owner = (await gateway.history.list(code, { category: 'owner' }))[0]
    expect(owner).toMatchObject({ before: '김영업', after: '박영업', by: { id: 'u-kim' }, at: TEST_NOW })
    expect((await gateway.history.list(code, { category: 'amount' }))[0]).toMatchObject({ before: '420,000,000원', after: '777,000,000원' })
  })

  it('Owner를 퇴사자로 지정하거나 퇴사 Owner를 유지한 채 저장하면 422', async () => {
    const { gateway } = await mockAs('kim')
    const msg = '퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.'
    await expectApiError(gateway.deals.update(dealCode(2), { ownerId: 'u-old' }), 422, msg)
    await expectApiError(gateway.deals.update(dealCode(23), { ownerId: 'u-old', name: '이름 수정' }), 422, msg)
    // Owner 필드를 보내지 않으면 퇴사 Owner Deal도 다른 필드는 고칠 수 있다.
    await gateway.deals.update(dealCode(23), { procurement: '메모' })
    const fixed = await gateway.deals.update(dealCode(23), { ownerId: 'u-park' })
    expect(fixed.owner.id).toBe('u-park')
    await expectApiError(gateway.deals.update(dealCode(2), { ownerId: 'u-root' }), 422)
  })

  it('실패한 수정은 아무것도 바꾸지 않는다(원자성)', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = await gateway.deals.get(code)
    await expectApiError(gateway.deals.update(code, { name: '바뀌면 안 됨', revenueAmount: -1 }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
    expect((await gateway.deals.get(code)).name).toBe(before.name)
    await expectApiError(
      gateway.deals.update(code, { name: '바뀌면 안 됨', customer: { contactId: null, company: '새 회사', name: 'x', title: '', email: null, phone: null } }),
      422,
    )
    expect(await gateway.contacts.companies('customer')).not.toContain('새회사')
  })

  it('Status/Forecast 폼 저장은 불변식을 만족해야 하고 둘 다 기록된다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    await expectApiError(gateway.deals.update(code, { statusKey: 'contract_completed' }), 422, 'Status와 Forecast의 동기화가 맞지 않습니다.')
    await expectApiError(gateway.deals.update(code, { forecastKey: 'won' }), 422, 'Status와 Forecast의 동기화가 맞지 않습니다.')
    const base = (await gateway.history.list(code, {})).length
    const done = await gateway.deals.update(code, { statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 400_000_000, revenueDate: '2026-10-14' })
    expect([done.statusKey, done.forecastKey]).toEqual(['contract_completed', 'won'])
    const cats = await categories(gateway, code, base)
    expect(cats).toEqual(expect.arrayContaining(['status', 'forecast', 'amount', 'expectedClose']))
    expect(done.risk).toBeNull()
  })

  it('파트너: 추가, 교체(이전은 비활성 이력으로 남음), 제거', async () => {
    const { gateway } = await mockAs('kim')
    // 추가(Deal 5는 파트너 없음)
    const added = await gateway.deals.update(dealCode(5), { partner: { contactId: null, company: '코어테크', name: '민지훈', title: '', email: null, phone: null } })
    expect(added.activePartner?.company).toBe('코어테크')
    expect((await gateway.history.list(dealCode(5), { category: 'partner' }))[0]).toMatchObject({ before: '없음', after: '코어테크 민지훈' })
    // 교체(Deal 17은 이미 교체 이력 1건)
    const swapped = await gateway.deals.update(dealCode(17), { partner: { contactId: null, company: '시큐어원', name: '조예린', title: '', email: null, phone: null } })
    expect(swapped.activePartner?.company).toBe('시큐어원')
    expect(swapped.partnerHistory).toHaveLength(3)
    expect(swapped.partnerHistory.filter((p) => p.active)).toHaveLength(1)
    expect(swapped.partnerHistory.every((p) => p.active || p.unlinkedAt !== null)).toBe(true)
    expect((await gateway.history.list(dealCode(17), { category: 'partner' }))[0]).toMatchObject({ before: '에이원시스템 표성호', after: '시큐어원 조예린' })
    // 같은 파트너를 다시 고르면 변화 없음
    const history = (await gateway.history.list(dealCode(17), {})).length
    await gateway.deals.update(dealCode(17), { partner: { contactId: null, company: '시큐어원', name: '조예린', title: '', email: null, phone: null } })
    expect((await gateway.history.list(dealCode(17), {})).length).toBe(history)
    // 제거
    const removed = await gateway.deals.update(dealCode(17), { partner: null })
    expect(removed.activePartner).toBeNull()
    expect((await gateway.history.list(dealCode(17), { category: 'partner' }))[0]).toMatchObject({ after: '없음' })
    // 파트너 일부만 입력하면 422
    await expectApiError(
      gateway.deals.update(dealCode(5), { partner: { contactId: null, company: '코어테크', name: '', title: '', email: null, phone: null } }),
      422,
      '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.',
    )
  })

  it('고객 연락처를 다른 사람으로 바꾸면 contact History가 남는다', async () => {
    const { gateway } = await mockAs('kim')
    const oh = await contactIdOf(gateway, 'customer', '한빛은행', '오지현')
    const updated = await gateway.deals.update(dealCode(1), { customer: { contactId: oh, company: '한빛은행', name: '오지현', title: '차장', email: null, phone: null } })
    expect(updated.customerContactId).toBe(oh)
    expect((await gateway.history.list(dealCode(1), { category: 'contact' }))[0]).toMatchObject({ before: '한빛은행 정민수', after: '한빛은행 오지현' })
  })
})
