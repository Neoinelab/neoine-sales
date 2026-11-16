import { describe, expect, it } from 'vitest'
import type { DealPatch } from '../../../shared/model/inputs'
import type { HistoryCategory } from '../../../shared/model/types'
import { seedVendorId } from '../../fixtures/vendors'
import { contactIdOf, dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

async function categories(gw: Awaited<ReturnType<typeof mockAs>>['gateway'], code: string, since: number) {
  const all = await gw.history.list(code, {})
  return all.slice(0, all.length - since).map((h) => h.category)
}

describe('deals.update', () => {
  it('조회자의 수정은 403이고 없는 code는 404다', async () => {
    // given: 조회자와 영업으로 로그인한 mock
    const han = await mockAs('han')
    const kim = await mockAs('kim')

    // when·then: 조회자가 수정하면 403이다
    await expectApiError(han.gateway.deals.update(dealCode(1), { name: 'x' }), 403)
    // when·then: 영업이 없는 code를 수정하면 404다
    await expectApiError(kim.gateway.deals.update('20000101-ZZZZ', { name: 'x' }), 404)
  })

  it('변경이 없으면 History도 updatedAt도 바뀌지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = await gateway.deals.get(code)
    const historyBefore = (await gateway.history.list(code, {})).length

    // when: 현재 값과 같은 값으로 수정한다
    await gateway.deals.update(code, { name: before.name, revenueAmount: before.revenueAmount })

    // then: 이력 수와 updatedAt이 그대로다
    expect((await gateway.history.list(code, {})).length).toBe(historyBefore)
    expect((await gateway.deals.get(code)).updatedAt).toBe(before.updatedAt)
  })

  it('바뀐 필드마다 이력이 남는다(Owner/금액/Expected Close/Label/견적/POC/기타)', async () => {
    // given: 현재 이력 수와 예산 Label
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length
    const labels = await gateway.labels.list()
    const budget = labels.find((l) => l.category === 'budget')
    if (!budget) throw new Error('label')

    // when: 여러 필드를 한 번에 수정한다
    const updated = await gateway.deals.update(code, {
      name: '대한제조 MFA 확대(수정)',
      ownerId: USER_ID.park,
      revenueAmount: 777_000_000,
      revenueDate: '2026-12-31',
      vendorId: seedVendorId('Okta'),
      product: 'SSO',
      users: 250,
      bant: { budget: { id: budget.id }, authority: null, need: null, timeline: null },
      quote: { submitted: 'YES', submittedDate: '2026-10-10' },
      poc: { state: 'ING', completedDate: null },
      procurement: '연말 일괄 구매',
    })

    // then: 값이 반영되고 구분별 이력이 남는다 (Owner·금액 이력은 이전·이후 값과 변경자·시각 포함)
    expect(updated).toMatchObject({ name: '대한제조 MFA 확대(수정)', owner: { id: USER_ID.park }, revenueAmount: 777_000_000, updatedAt: TEST_NOW })
    const cats = await categories(gateway, code, base)
    const expected: HistoryCategory[] = ['owner', 'amount', 'expectedClose', 'bant', 'other']
    for (const c of expected) expect(cats).toContain(c)
    expect(cats.filter((c) => c === 'other').length).toBe(7) // 이름, Vendor, Product, Users count, 견적, POC, 구매절차
    const owner = (await gateway.history.list(code, { category: 'owner' }))[0]
    expect(owner).toMatchObject({ before: '김영업', after: '박영업', by: { id: USER_ID.kim }, at: TEST_NOW })
    expect((await gateway.history.list(code, { category: 'amount' }))[0]).toMatchObject({ target: '금액(단위:원)', before: '420,000,000', after: '777,000,000' })
  })

  it('Users count를 비우는 수정은 거절하고 값을 유지한다', async () => {
    // given: 현재 값과 이력 수
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = await gateway.deals.get(code)
    const history = (await gateway.history.list(code, {})).length

    // when·then: Users count를 null로 수정하면 422다
    await expectApiError(gateway.deals.update(code, { users: null } as unknown as DealPatch), 422, 'Users count를 입력하세요.')

    // then: 값과 이력 수가 그대로다
    expect((await gateway.deals.get(code)).users).toBe(before.users)
    expect((await gateway.history.list(code, {})).length).toBe(history)
  })

  it('음수·소수 Users count는 0 이상 정수 문구로 거절한다', async () => {
    // given: 영업으로 로그인한 mock
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when·then: -1과 2.5로 수정하면 모두 0 이상 정수 문구와 함께 422다
    await expectApiError(gateway.deals.update(code, { users: -1 }), 422, 'Users count는 0 이상의 정수로 입력하세요.')
    await expectApiError(gateway.deals.update(code, { users: 2.5 }), 422, 'Users count는 0 이상의 정수로 입력하세요.')
  })

  it('Users count 0을 받아들이고 이력에 남긴다', async () => {
    // given: 현재 Users count
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = await gateway.deals.get(code)

    // when: Users count를 0으로 수정한다
    const updated = await gateway.deals.update(code, { users: 0 })
    const entry = (await gateway.history.list(code, { category: 'other' }))[0]

    // then: 0으로 바뀌고 이전·이후 값이 이력에 남는다
    expect(updated.users).toBe(0)
    expect(entry).toMatchObject({ target: 'Users count', before: String(before.users), after: '0' })
  })

  it('비운 Users count보다 Deal Name 오류를 먼저 알린다', async () => {
    // given: 영업으로 로그인한 mock
    const { gateway } = await mockAs('kim')

    // when·then: 이름과 Users count를 모두 비우면 Deal Name 문구로 422다
    await expectApiError(
      gateway.deals.update(dealCode(2), { name: '', users: null } as unknown as DealPatch),
      422,
      'Deal Name을 입력하세요.',
    )
  })

  it('Owner를 퇴사자로 지정하거나 퇴사 Owner를 유지한 채 저장하면 422다', async () => {
    // given: 영업으로 로그인한 mock과 퇴사자 안내 문구
    const { gateway } = await mockAs('kim')
    const msg = '퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.'

    // when·then: 퇴사자를 Owner로 지정하면 422다
    await expectApiError(gateway.deals.update(dealCode(2), { ownerId: USER_ID.old }), 422, msg)
    await expectApiError(gateway.deals.update(dealCode(23), { ownerId: USER_ID.old, name: '이름 수정' }), 422, msg)
    // when: Owner 필드를 보내지 않고 다른 필드만 고친 뒤 재직자로 바꾼다 (퇴사 Owner Deal도 다른 필드는 고칠 수 있다)
    await gateway.deals.update(dealCode(23), { procurement: '메모' })
    const fixed = await gateway.deals.update(dealCode(23), { ownerId: USER_ID.park })
    // then: 새 Owner로 바뀐다
    expect(fixed.owner.id).toBe(USER_ID.park)
    // when·then: 관리자를 Owner로 지정해도 422다
    await expectApiError(gateway.deals.update(dealCode(2), { ownerId: USER_ID.root }), 422)
  })

  it('실패한 수정은 아무것도 바꾸지 않는다(원자성)', async () => {
    // given: 현재 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = await gateway.deals.get(code)

    // when·then: 이름과 잘못된 매출금액을 함께 수정하면 422다
    await expectApiError(gateway.deals.update(code, { name: '바뀌면 안 됨', revenueAmount: -1 }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
    // then: 이름이 바뀌지 않는다
    expect((await gateway.deals.get(code)).name).toBe(before.name)
    // when·then: 이름과 잘못된 고객 연락처를 함께 수정하면 422다
    await expectApiError(
      gateway.deals.update(code, { name: '바뀌면 안 됨', customer: { contactId: null, company: '새 회사', name: 'x', title: '', email: null, phone: null } }),
      422,
    )
    // then: 새 고객 회사가 만들어지지 않는다
    expect(await gateway.contacts.companies('customer')).not.toContain('새회사')
  })

  it('Status/Forecast 폼 저장은 불변식을 만족해야 하고 둘 다 기록된다', async () => {
    // given: 영업으로 로그인한 mock
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when·then: Status만 계약완료로 또는 Forecast만 Won으로 바꾸면 동기화 문구와 함께 422다
    await expectApiError(gateway.deals.update(code, { statusKey: 'contract_completed' }), 422, 'Status와 Forecast의 동기화가 맞지 않습니다.')
    await expectApiError(gateway.deals.update(code, { forecastKey: 'won' }), 422, 'Status와 Forecast의 동기화가 맞지 않습니다.')
    const base = (await gateway.history.list(code, {})).length

    // when: Status·Forecast·매출 값을 함께 맞춰 수정한다
    const done = await gateway.deals.update(code, { statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 400_000_000, revenueDate: '2026-10-14' })
    const cats = await categories(gateway, code, base)

    // then: 둘 다 바뀌고 status·forecast·amount·expectedClose 이력이 남으며 경고는 없다
    expect([done.statusKey, done.forecastKey]).toEqual(['contract_completed', 'won'])
    expect(cats).toEqual(expect.arrayContaining(['status', 'forecast', 'amount', 'expectedClose']))
    expect(done.risk).toBeNull()
  })

  it('파트너를 추가하고 교체하고(이전은 비활성 이력으로 남음) 제거한다', async () => {
    // given: 영업으로 로그인한 mock (Deal 5는 파트너 없음, Deal 17은 교체 이력 1건)
    const { gateway } = await mockAs('kim')

    // when: Deal 5에 파트너를 추가한다
    const added = await gateway.deals.update(dealCode(5), { partner: { contactId: null, company: '코어테크', name: '민지훈', title: '', email: null, phone: null } })
    // then: 활성 파트너가 되고 이력에 '없음 → 코어테크 민지훈'이 남는다
    expect(added.activePartner?.company).toBe('코어테크')
    expect((await gateway.history.list(dealCode(5), { category: 'partner' }))[0]).toMatchObject({ before: '없음', after: '코어테크 민지훈' })
    // when: Deal 17의 파트너를 다른 파트너로 교체한다
    const swapped = await gateway.deals.update(dealCode(17), { partner: { contactId: null, company: '시큐어원', name: '조예린', title: '', email: null, phone: null } })
    // then: 새 파트너가 활성이고 이전 파트너는 비활성 이력으로 남으며 교체 이력이 기록된다
    expect(swapped.activePartner?.company).toBe('시큐어원')
    expect(swapped.partnerHistory).toHaveLength(3)
    expect(swapped.partnerHistory.filter((p) => p.active)).toHaveLength(1)
    expect(swapped.partnerHistory.every((p) => p.active || p.unlinkedAt !== null)).toBe(true)
    expect((await gateway.history.list(dealCode(17), { category: 'partner' }))[0]).toMatchObject({ before: '에이원시스템 표성호', after: '시큐어원 조예린' })
    const history = (await gateway.history.list(dealCode(17), {})).length
    // when: 같은 파트너를 다시 고른다
    await gateway.deals.update(dealCode(17), { partner: { contactId: null, company: '시큐어원', name: '조예린', title: '', email: null, phone: null } })
    // then: 이력 수가 그대로다
    expect((await gateway.history.list(dealCode(17), {})).length).toBe(history)
    // when: 파트너를 제거한다
    const removed = await gateway.deals.update(dealCode(17), { partner: null })
    // then: 활성 파트너가 없고 이력에 '없음'이 남는다
    expect(removed.activePartner).toBeNull()
    expect((await gateway.history.list(dealCode(17), { category: 'partner' }))[0]).toMatchObject({ after: '없음' })
    // when·then: 파트너 일부만 입력하면 회사명·담당자명 필요 문구와 함께 422다
    await expectApiError(
      gateway.deals.update(dealCode(5), { partner: { contactId: null, company: '코어테크', name: '', title: '', email: null, phone: null } }),
      422,
      '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.',
    )
  })

  it('고객 연락처를 다른 사람으로 바꾸면 contact 이력이 남는다', async () => {
    // given: 같은 회사의 다른 고객 연락처
    const { gateway } = await mockAs('kim')
    const oh = await contactIdOf(gateway, 'customer', '한빛은행', '오지현')

    // when: Deal의 고객 연락처를 그 사람으로 바꾼다
    const updated = await gateway.deals.update(dealCode(1), { customer: { contactId: oh, company: '한빛은행', name: '오지현', title: '차장', email: null, phone: null } })

    // then: 연락처가 바뀌고 이전·이후 사람이 contact 이력에 남는다
    expect(updated.customerContactId).toBe(oh)
    expect((await gateway.history.list(dealCode(1), { category: 'contact' }))[0]).toMatchObject({ before: '한빛은행 정민수', after: '한빛은행 오지현' })
  })
})
