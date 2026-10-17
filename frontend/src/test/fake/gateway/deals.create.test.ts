import { describe, expect, it } from 'vitest'
import { DEAL_CODE_PATTERN } from '../../../shared/model/constants'
import { contactIdOf, dealCode, dealInput, expectApiError, mockAs, TEST_NOW } from '../testing'

describe('deals.create', () => {
  it('T-GW user는 403, 비로그인은 401', async () => {
    const han = await mockAs('han')
    await expectApiError(han.gateway.deals.create(dealInput('u-kim')), 403)
    const none = await mockAs(null)
    await expectApiError(none.gateway.deals.create(dealInput('u-kim')), 401)
  })

  it('T-GW-검증 422 문구', async () => {
    const { gateway } = await mockAs('kim')
    const create = (over: Parameters<typeof dealInput>[1]) => gateway.deals.create(dealInput('u-kim', over))
    await expectApiError(create({ name: '  ' }), 422, 'Deal Name을 입력하세요.')
    await expectApiError(create({ revenueAmount: 0 }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
    await expectApiError(create({ revenueAmount: 10.5 }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
    await expectApiError(create({ revenueDate: '' }), 422, 'Expected Close를 입력하세요.')
    await expectApiError(create({ users: 0 }), 422, 'Users는 1 이상의 정수로 입력하세요.')
    await expectApiError(create({ ownerId: 'u-old' }), 422)
    await expectApiError(create({ ownerId: 'u-root' }), 422, 'Owner는 재직 중인 영업 담당자여야 합니다.')
    await expectApiError(create({ ownerId: 'u-nobody' }), 422, 'Owner는 재직 중인 영업 담당자여야 합니다.')
    await expectApiError(create({ statusKey: 'contract_completed' }), 422, 'Status와 Forecast의 동기화가 맞지 않습니다.')
    await expectApiError(create({ forecastKey: 'won' }), 422, 'Status와 Forecast의 동기화가 맞지 않습니다.')
    await expectApiError(create({ statusKey: 'nope' }), 422)
    await expectApiError(
      create({ customer: { contactId: null, company: '', name: '정민수', title: '', email: null, phone: null } }),
      422,
      '고객 회사명을 입력하세요.',
    )
    await expectApiError(
      create({ customer: { contactId: null, company: '한빛은행', name: '', title: '', email: null, phone: null } }),
      422,
      '고객 담당자명을 입력하세요.',
    )
    await expectApiError(
      create({ partner: { contactId: null, company: '코어테크', name: '', title: '', email: null, phone: null } }),
      422,
      '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.',
    )
    await expectApiError(
      create({ customer: { contactId: null, company: '한 빛', name: '정민수', title: '', email: null, phone: null } }),
      422,
      '공백은 입력할 수 없습니다.',
    )
    await expectApiError(
      create({ customer: { contactId: null, company: '한빛은행', name: '정민수', title: '', email: 'bad', phone: null } }),
      422,
      '이메일 형식이 올바르지 않습니다.',
    )
    await expectApiError(create({ bant: { budget: 'l-none', authority: null, need: null, timeline: null } }), 422)
  })

  it('실패한 요청은 아무것도 바꾸지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const before = (await gateway.deals.list({ limit: 100 })).total
    await expectApiError(
      gateway.deals.create(
        dealInput('u-kim', {
          customer: { contactId: null, company: '신규회사', name: '신규인', title: '', email: null, phone: null },
          revenueAmount: 0,
        }),
      ),
      422,
    )
    expect((await gateway.deals.list({ limit: 100 })).total).toBe(before)
    expect(await gateway.contacts.companies('customer')).not.toContain('신규회사')
  })

  it('T-GW-code 등록하면 오늘 날짜 + 4자리 code가 채번되고 History 1건이 남는다', async () => {
    const { gateway } = await mockAs('kim')
    const deal = await gateway.deals.create(dealInput('u-kim'))
    expect(deal.code).toMatch(DEAL_CODE_PATTERN)
    expect(deal.code.startsWith('20261015-')).toBe(true)
    expect(deal).toMatchObject({ owner: { id: 'u-kim' }, statusKey: 'prospecting', forecastKey: 'pipeline', createdAt: TEST_NOW })
    const history = await gateway.history.list(deal.code, {})
    expect(history).toHaveLength(1)
    expect(history[0]).toMatchObject({ category: 'created', before: '', after: 'Deal 등록', at: TEST_NOW, by: { id: 'u-kim' } })
  })

  it('code는 여러 건을 만들어도 겹치지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const made = new Set<string>()
    for (let i = 0; i < 30; i += 1) made.add((await gateway.deals.create(dealInput('u-kim', { name: `D${i}` }))).code)
    expect(made.size).toBe(30)
  })

  it('T-CONTACT 이메일 없이 같은 회사+이름이면 기존 연락처를 쓰고, 새 사람이면 새 연락처를 만든다', async () => {
    const { gateway } = await mockAs('kim')
    const existing = await contactIdOf(gateway, 'customer', '한빛은행', '정민수')
    const same = await gateway.deals.create(dealInput('u-kim'))
    expect(same.customerContactId).toBe(existing)
    expect(await gateway.contacts.byCompany('customer', '한빛은행')).toHaveLength(3)
    const other = await gateway.deals.create(
      dealInput('u-kim', { customer: { contactId: null, company: '한빛은행', name: '신입사원', title: '사원', email: 'new@hanbit.test', phone: null } }),
    )
    expect(other.customerContactId).not.toBe(existing)
    expect(await gateway.contacts.byCompany('customer', '한빛은행')).toHaveLength(4)
    const brandNew = await gateway.deals.create(
      dealInput('u-kim', { customer: { contactId: null, company: '신규회사', name: '홍길동', title: '', email: null, phone: null } }),
    )
    expect(brandNew.customer.company).toBe('신규회사')
    expect(await gateway.contacts.companies('customer')).toContain('신규회사')
  })

  it('T-CONTACT 동명이인은 이메일로 구분한다', async () => {
    const { gateway } = await mockAs('kim')
    const bae1 = await contactIdOf(gateway, 'customer', '누리통신', '배성훈', '차장')
    const pickBae1 = await gateway.deals.create(
      dealInput('u-kim', { customer: { contactId: null, company: '누리통신', name: '배성훈', title: '차장', email: 'bae1@nuri.test', phone: null } }),
    )
    expect(pickBae1.customerContactId).toBe(bae1)
    const third = await gateway.deals.create(
      dealInput('u-kim', { customer: { contactId: null, company: '누리통신', name: '배성훈', title: '부장', email: 'bae3@nuri.test', phone: null } }),
    )
    expect(third.customerContactId).not.toBe(bae1)
    expect(await gateway.contacts.byCompany('customer', '누리통신')).toHaveLength(3)
  })

  it('contactId로 고른 연락처를 고쳐 저장하면 연락처가 갱신되고 다른 Deal에도 반영된다', async () => {
    const { gateway } = await mockAs('kim')
    const seo = await contactIdOf(gateway, 'customer', '대한제조', '서준영')
    const created = await gateway.deals.create(
      dealInput('u-kim', { customer: { contactId: seo, company: '대한제조', name: '서준영', title: '부장', email: 'seo-new@daehan.test', phone: '010-1111-2222' } }),
    )
    expect(created.customer).toMatchObject({ id: seo, title: '부장', email: 'seo-new@daehan.test', phone: '010-1111-2222' })
    const d14 = await gateway.deals.get(dealCode(14))
    expect(d14.customer.email).toBe('seo-new@daehan.test')
    const history = await gateway.history.list(dealCode(14), {})
    expect(history[0]).toMatchObject({ category: 'contact' })
    expect((await gateway.deals.get(dealCode(14))).updatedAt).toBe(TEST_NOW)
  })

  it('파트너를 함께 등록하면 활성 파트너가 된다', async () => {
    const { gateway } = await mockAs('kim')
    const deal = await gateway.deals.create(
      dealInput('u-kim', { partner: { contactId: null, company: '코어테크', name: '민지훈', title: '대표', email: null, phone: null } }),
    )
    expect(deal.activePartner).toMatchObject({ company: '코어테크', name: '민지훈' })
    expect(deal.partnerHistory).toHaveLength(1)
  })

  it('admin은 다른 영업 담당자를 Owner로 등록할 수 있다', async () => {
    const { gateway } = await mockAs('root')
    const deal = await gateway.deals.create(dealInput('u-lee'))
    expect(deal.owner.id).toBe('u-lee')
  })
})
