import { describe, expect, it } from 'vitest'
import type { ContactInput } from '../../../shared/model/types'
import { contactIdOf, dealCode, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID } from '../seed/ids'

const person = (over: Partial<ContactInput> = {}): ContactInput => ({
  company: '신규회사',
  name: '홍길동',
  title: '과장',
  email: 'hong@new.test',
  phone: '010-1234-5678',
  ...over,
})

describe('contacts 조회', () => {
  it('T-CONTACT-03 companies는 구분별 distinct, byCompany는 대소문자 무시·dealCount 포함', async () => {
    const { gateway } = await mockAs('kim')
    const customers = await gateway.contacts.companies('customer')
    expect(customers).toHaveLength(12)
    expect(new Set(customers.map((c) => c.toLowerCase())).size).toBe(12)
    const rows = await gateway.contacts.byCompany('customer', '한빛은행'.toUpperCase())
    expect(rows.map((r) => r.name)).toEqual(['오지현', '임태호', '정민수'])
    expect(rows.find((r) => r.name === '정민수')?.dealCount).toBe(1)
    expect((await gateway.contacts.byCompany('customer', '대한제조')).find((r) => r.name === '서준영')?.dealCount).toBe(2)
    expect(await gateway.contacts.byCompany('customer', '없는회사')).toEqual([])
  })

  it('list는 구분·키워드 필터와 페이지네이션을 지원한다', async () => {
    const { gateway } = await mockAs('root')
    expect((await gateway.contacts.list({ kind: 'partner' })).total).toBe(7)
    expect((await gateway.contacts.list({ kind: 'customer' })).total).toBe(17)
    const page1 = await gateway.contacts.list({})
    expect(page1.items).toHaveLength(20)
    expect((await gateway.contacts.list({ offset: 20 })).items).toHaveLength(4)
    expect((await gateway.contacts.list({ keyword: 'NURI' })).items.map((c) => c.company)).toEqual(['누리통신', '누리통신'])
    expect((await gateway.contacts.list({ keyword: '표성호' })).total).toBe(1)
  })
})

describe('contacts 관리(admin)', () => {
  it('T-CONTACT 변경은 admin만(sales·user 403)', async () => {
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      await expectApiError(gateway.contacts.create('customer', person()), 403)
      await expectApiError(gateway.contacts.update(1, person()), 403)
      await expectApiError(gateway.contacts.remove(1), 403)
    }
  })

  it('T-CONTACT-02 공백은 422 "공백은 입력할 수 없습니다."', async () => {
    const { gateway } = await mockAs('root')
    const msg = '공백은 입력할 수 없습니다.'
    await expectApiError(gateway.contacts.create('customer', person({ company: '신규 회사' })), 422, msg)
    await expectApiError(gateway.contacts.create('customer', person({ name: '홍 길동' })), 422, msg)
    await expectApiError(gateway.contacts.create('customer', person({ email: 'a b@c.test' })), 422, msg)
    await expectApiError(gateway.contacts.create('customer', person({ phone: '010 1234' })), 422, msg)
    await expectApiError(gateway.contacts.create('customer', person({ email: 'invalid' })), 422, '이메일 형식이 올바르지 않습니다.')
    await expectApiError(gateway.contacts.create('customer', person({ company: '' })), 422)
  })

  it('등록하면 목록에 나오고 이메일이 빈 문자열이면 null로 저장한다', async () => {
    const { gateway } = await mockAs('root')
    const created = await gateway.contacts.create('partner', person({ email: '', phone: '' }))
    expect(created).toMatchObject({ kind: 'partner', company: '신규회사', email: null, phone: null })
    expect(await gateway.contacts.companies('partner')).toContain('신규회사')
  })

  it('이미 같은 사람이 있으면 409', async () => {
    const { gateway } = await mockAs('root')
    await expectApiError(gateway.contacts.create('customer', person({ company: '한빛은행', name: '오지현', email: null })), 409, '이미 등록된 연락처입니다.')
    // 이메일이 다른 동명이인은 허용
    await gateway.contacts.create('customer', person({ company: '누리통신', name: '배성훈', email: 'bae9@nuri.test' }))
    expect(await gateway.contacts.byCompany('customer', '누리통신')).toHaveLength(3)
  })

  it('T-CONTACT 수정은 공유 중인 모든 Deal에 반영되고 각 Deal History에 남는다', async () => {
    const { gateway } = await mockAs('root')
    const seo = await contactIdOf(gateway, 'customer', '대한제조', '서준영')
    const updated = await gateway.contacts.update(seo, person({ company: '대한제조', name: '서준영', email: 'seo@daehan.test', title: '이사' }))
    expect(updated).toMatchObject({ id: seo, title: '이사', email: 'seo@daehan.test' })
    for (const no of [2, 14]) {
      const deal = await gateway.deals.get(dealCode(no))
      expect(deal.customer).toMatchObject({ title: '이사', email: 'seo@daehan.test' })
      expect((await gateway.history.list(dealCode(no), { category: 'contact' }))[0]).toBeTruthy()
    }
    await expectApiError(gateway.contacts.update(NO_SUCH_ID, person()), 404)
  })

  it('수정 결과가 다른 연락처와 같은 사람이 되면 409', async () => {
    const { gateway } = await mockAs('root')
    const bae2 = await contactIdOf(gateway, 'customer', '누리통신', '배성훈', '과장')
    await expectApiError(
      gateway.contacts.update(bae2, person({ company: '누리통신', name: '배성훈', email: 'bae1@nuri.test' })),
      409,
      '이미 등록된 연락처입니다.',
    )
  })

  it('참조 중인 연락처 삭제는 409(N건 안내), 참조 없으면 삭제된다', async () => {
    const { gateway } = await mockAs('root')
    const jung = await contactIdOf(gateway, 'customer', '한빛은행', '정민수')
    await expectApiError(gateway.contacts.remove(jung), 409, '연결된 Deal이 1건 있어 삭제할 수 없습니다.')
    const seo = await contactIdOf(gateway, 'customer', '대한제조', '서준영')
    await expectApiError(gateway.contacts.remove(seo), 409, '연결된 Deal이 2건 있어 삭제할 수 없습니다.')
    const lonely = await gateway.contacts.create('customer', person())
    await gateway.contacts.remove(lonely.id)
    expect(await gateway.contacts.companies('customer')).not.toContain('신규회사')
    await expectApiError(gateway.contacts.remove(lonely.id), 404)
  })

  it('Deal을 지워 참조가 없어지면 삭제할 수 있다', async () => {
    const { gateway } = await mockAs('root')
    const jung = await contactIdOf(gateway, 'customer', '한빛은행', '정민수')
    await gateway.deals.remove(dealCode(1), dealCode(1))
    await gateway.contacts.remove(jung)
    expect((await gateway.contacts.byCompany('customer', '한빛은행')).map((c) => c.name)).not.toContain('정민수')
  })

  it('비활성 파트너 링크가 있어도 참조 중으로 본다', async () => {
    const { gateway } = await mockAs('root')
    const core = await contactIdOf(gateway, 'partner', '코어테크', '민지훈')
    await gateway.deals.update(dealCode(17), { partner: null }) // 17의 에이원시스템 비활성
    const ay = await contactIdOf(gateway, 'partner', '에이원시스템', '표성호')
    await expectApiError(gateway.contacts.remove(ay), 409, /연결된 Deal이 \d+건 있어 삭제할 수 없습니다\./)
    await expectApiError(gateway.contacts.remove(core), 409)
  })
})
