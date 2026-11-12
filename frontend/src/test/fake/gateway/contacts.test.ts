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
  // Fake 게이트웨이의 회사 목록은 구분별 distinct이고 회사별 담당자는 대소문자를 무시하며 dealCount를 담는다
  it('T-CONTACT-03 companies는 구분별 distinct, byCompany는 대소문자 무시·dealCount 포함', async () => {
    // given: admin이 아닌 sales로 로그인한 Fake
    const { gateway } = await mockAs('kim')

    // when: 회사 목록과 회사별 담당자를 읽는다
    const customers = await gateway.contacts.companies('customer')

    // then: 서버 규칙과 같은 목록과 dealCount가 나온다
    expect(customers).toHaveLength(12)
    expect(new Set(customers.map((c) => c.toLowerCase())).size).toBe(12)
    const rows = await gateway.contacts.byCompany('customer', '한빛은행'.toUpperCase())
    expect(rows.map((r) => r.name)).toEqual(['오지현', '임태호', '정민수'])
    expect(rows.find((r) => r.name === '정민수')?.dealCount).toBe(1)
    expect((await gateway.contacts.byCompany('customer', '대한제조')).find((r) => r.name === '서준영')?.dealCount).toBe(2)
    expect(await gateway.contacts.byCompany('customer', '없는회사')).toEqual([])
  })

  // Fake 목록은 구분·키워드 필터와 페이지를 지원한다
  it('list는 구분·키워드 필터와 페이지네이션을 지원한다', async () => {
    // when: 구분·키워드·offset으로 읽는다 (전제: admin으로 로그인한 Fake)
    const { gateway } = await mockAs('root')

    // then: 서버와 같은 건수와 항목이 나온다
    expect((await gateway.contacts.list({ kind: 'partner' })).total).toBe(7)
    expect((await gateway.contacts.list({ kind: 'customer' })).total).toBe(17)
    const page1 = await gateway.contacts.list({ limit: 20 })
    expect(page1.items).toHaveLength(20)
    expect((await gateway.contacts.list({ offset: 20, limit: 20 })).items).toHaveLength(4)
    expect((await gateway.contacts.list({ keyword: 'NURI' })).items.map((c) => c.company)).toEqual(['누리통신', '누리통신'])
    expect((await gateway.contacts.list({ keyword: '표성호' })).total).toBe(1)
  })
})

describe('contacts 관리(admin)', () => {
  // Fake의 쓰기는 admin만 허용하고 sales·user는 403이다
  it('T-CONTACT 변경은 admin만(sales·user 403)', async () => {
    // when·then: 등록·수정·삭제를 시도한다 → 모두 403이다 (전제: sales와 user로 로그인한 Fake)
    for (const key of ['kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      await expectApiError(gateway.contacts.create('customer', person()), 403)
      await expectApiError(gateway.contacts.update(1, person()), 403)
      await expectApiError(gateway.contacts.remove(1), 403)
    }
  })

  // Fake는 공백·형식 위반을 422로 거절한다
  it('T-CONTACT-02 공백은 422 "공백은 입력할 수 없습니다."', async () => {
    // given: admin으로 로그인한 Fake
    const { gateway } = await mockAs('root')
    const msg = '공백은 입력할 수 없습니다.'

    // when·then: 공백·틀린 이메일·빈 회사명으로 등록한다 → 공백 문구, 이메일 형식 문구, 422가 나온다
    await expectApiError(gateway.contacts.create('customer', person({ company: '신규 회사' })), 422, msg)
    await expectApiError(gateway.contacts.create('customer', person({ name: '홍 길동' })), 422, msg)
    await expectApiError(gateway.contacts.create('customer', person({ email: 'a b@c.test' })), 422, msg)
    await expectApiError(gateway.contacts.create('customer', person({ phone: '010 1234' })), 422, msg)
    await expectApiError(gateway.contacts.create('customer', person({ email: 'invalid' })), 422, '이메일 형식이 올바르지 않습니다.')
    await expectApiError(gateway.contacts.create('customer', person({ company: '' })), 422)
  })

  // Fake는 이메일·전화의 빈 문자열을 null로 저장하고 등록한 회사를 목록에 낸다
  it('등록하면 목록에 나오고 이메일이 빈 문자열이면 null로 저장한다', async () => {
    // given: admin으로 로그인한 Fake
    const { gateway } = await mockAs('root')

    // when: 이메일·전화가 빈 문자열인 파트너를 등록한다
    const created = await gateway.contacts.create('partner', person({ email: '', phone: '' }))

    // then: null로 저장되고 파트너 회사 목록에 나온다
    expect(created).toMatchObject({ kind: 'partner', company: '신규회사', email: null, phone: null })
    expect(await gateway.contacts.companies('partner')).toContain('신규회사')
  })

  // Fake는 같은 사람 등록을 409로 거절하고 동명이인은 허용한다
  it('이미 같은 사람이 있으면 409', async () => {
    // when: 같은 사람과 다른 이메일의 동명이인을 등록한다 (전제: 이메일 없는 연락처와 이메일 있는 연락처)
    const { gateway } = await mockAs('root')

    // then: 같은 사람은 409, 동명이인은 저장된다
    await expectApiError(gateway.contacts.create('customer', person({ company: '한빛은행', name: '오지현', email: null })), 409, '이미 등록된 연락처입니다.')
    // 이메일이 다른 동명이인은 허용
    await gateway.contacts.create('customer', person({ company: '누리통신', name: '배성훈', email: 'bae9@nuri.test' }))
    expect(await gateway.contacts.byCompany('customer', '누리통신')).toHaveLength(3)
  })

  // Fake의 연락처 수정은 쓰는 모든 Deal에 반영되고 각 Deal History에 남는다
  it('T-CONTACT 수정은 공유 중인 모든 Deal에 반영되고 각 Deal History에 남는다', async () => {
    // given: Deal 2건이 쓰는 고객 연락처
    const { gateway } = await mockAs('root')
    const seo = await contactIdOf(gateway, 'customer', '대한제조', '서준영')

    // when: 직급과 이메일을 수정한다
    const updated = await gateway.contacts.update(seo, person({ company: '대한제조', name: '서준영', email: 'seo@daehan.test', title: '이사' }))

    // then: 두 Deal의 연락처와 History에 반영되고 없는 id는 404다
    expect(updated).toMatchObject({ id: seo, title: '이사', email: 'seo@daehan.test' })
    for (const no of [2, 14]) {
      const deal = await gateway.deals.get(dealCode(no))
      expect(deal.customer).toMatchObject({ title: '이사', email: 'seo@daehan.test' })
      expect((await gateway.history.list(dealCode(no), { category: 'contact' }))[0]).toBeTruthy()
    }
    await expectApiError(gateway.contacts.update(NO_SUCH_ID, person()), 404)
  })

  // Fake는 수정 결과가 다른 연락처와 같은 사람이 되면 409로 거절한다
  it('수정 결과가 다른 연락처와 같은 사람이 되면 409', async () => {
    // given: 이메일이 다른 동명이인 두 건
    const { gateway } = await mockAs('root')

    // when: 한 건의 이메일을 다른 건과 같게 수정한다
    const bae2 = await contactIdOf(gateway, 'customer', '누리통신', '배성훈', '과장')

    // then: 409 문구다
    await expectApiError(
      gateway.contacts.update(bae2, person({ company: '누리통신', name: '배성훈', email: 'bae1@nuri.test' })),
      409,
      '이미 등록된 연락처입니다.',
    )
  })

  // Fake는 참조 중인 연락처 삭제를 건수 문구와 함께 409로 거절한다
  it('참조 중인 연락처 삭제는 409(N건 안내), 참조 없으면 삭제된다', async () => {
    // given: Deal이 쓰는 연락처와 쓰지 않는 연락처
    const { gateway } = await mockAs('root')

    // when: 각각 삭제한다
    const jung = await contactIdOf(gateway, 'customer', '한빛은행', '정민수')

    // then: 쓰는 연락처는 건수 문구의 409, 쓰지 않는 연락처는 삭제되고 다시 삭제하면 404다
    await expectApiError(gateway.contacts.remove(jung), 409, '연결된 Deal이 1건 있어 삭제할 수 없습니다.')
    const seo = await contactIdOf(gateway, 'customer', '대한제조', '서준영')
    await expectApiError(gateway.contacts.remove(seo), 409, '연결된 Deal이 2건 있어 삭제할 수 없습니다.')
    const lonely = await gateway.contacts.create('customer', person())
    await gateway.contacts.remove(lonely.id)
    expect(await gateway.contacts.companies('customer')).not.toContain('신규회사')
    await expectApiError(gateway.contacts.remove(lonely.id), 404)
  })

  // 참조하던 Deal을 지우면 Fake에서 연락처를 삭제할 수 있다
  it('Deal을 지워 참조가 없어지면 삭제할 수 있다', async () => {
    // given: Deal 한 건이 쓰는 연락처
    const { gateway } = await mockAs('root')
    const jung = await contactIdOf(gateway, 'customer', '한빛은행', '정민수')
    await gateway.deals.remove(dealCode(1), dealCode(1))
    await gateway.contacts.remove(jung)

    // when: Deal을 지우고 연락처를 삭제한다
    const actual = (await gateway.contacts.byCompany('customer', '한빛은행')).map((c) => c.name)

    // then: 목록에서 사라진다
    expect(actual).not.toContain('정민수')
  })

  // Fake는 비활성 파트너 링크도 참조로 보고 삭제를 거절한다
  it('비활성 파트너 링크가 있어도 참조 중으로 본다', async () => {
    // given: 파트너가 교체돼 옛 링크가 비활성인 Deal
    const { gateway } = await mockAs('root')
    const core = await contactIdOf(gateway, 'partner', '코어테크', '민지훈')
    await gateway.deals.update(dealCode(17), { partner: null }) // 17의 에이원시스템 비활성
    const ay = await contactIdOf(gateway, 'partner', '에이원시스템', '표성호')

    // when·then: 옛 파트너와 현재 파트너를 삭제한다 → 둘 다 409다
    await expectApiError(gateway.contacts.remove(ay), 409, /연결된 Deal이 \d+건 있어 삭제할 수 없습니다\./)
    await expectApiError(gateway.contacts.remove(core), 409)
  })
})

describe('contacts Fake가 서버 규칙을 따른다 (CT-R4, R6, R9, R13~R15)', () => {
  // 이메일은 소문자로 저장한다
  it('lowercases the email on create', async () => {
    // given: admin으로 로그인한 Fake
    const { gateway } = await mockAs('root')
    // when: 대문자 이메일로 등록한다
    const created = await gateway.contacts.create('customer', person({ email: 'Hong@New.Test' }))
    // then: 소문자로 저장된다
    expect(created.email).toBe('hong@new.test')
  })

  // 값이 같아도 수정하면 수정 시각이 서버 시각으로 갱신된다
  it('refreshes updatedAt even when nothing changed', async () => {
    // given: 방금 등록한 연락처와 그 뒤 흐른 시간
    const { gateway, clock } = await mockAs('root')
    const created = await gateway.contacts.create('customer', person())
    clock.advance(60_000)
    // when: 같은 값으로 수정한다
    const updated = await gateway.contacts.update(created.id, person())
    // then: 값은 그대로이고 수정 시각만 바뀐다
    expect(updated.company).toBe(created.company)
    expect(updated.createdAt).toBe(created.createdAt)
    expect(updated.updatedAt).not.toBe(created.updatedAt)
  })

  // 정렬은 소문자 코드 포인트 순이다
  it('orders companies and people by lowercase code point', async () => {
    // given: 대소문자와 한글이 섞인 회사
    const { gateway } = await mockAs('root')
    for (const company of ['beta', 'Zulu', 'alpha']) {
      await gateway.contacts.create('partner', person({ company, name: '가', email: null }))
    }
    // when: 파트너 회사 목록과 관리 목록을 읽는다
    const companies = await gateway.contacts.companies('partner')
    const listed = await gateway.contacts.list({ kind: 'partner' })
    // then: 소문자 코드 포인트 순이다
    expect(companies.filter((c) => ['alpha', 'beta', 'Zulu'].includes(c))).toEqual(['alpha', 'beta', 'Zulu'])
    expect(listed.items.map((c) => c.company).filter((c) => ['alpha', 'beta', 'Zulu'].includes(c))).toEqual(['alpha', 'beta', 'Zulu'])
  })

  // 첫 오류는 서버 판정 순서(공백 → 이메일 → 전화 → 회사명 → 담당자명)를 따른다
  it('reports the first error in the server order', async () => {
    // given: admin으로 로그인한 Fake
    const { gateway } = await mockAs('root')
    // when·then: 빈 회사명과 틀린 이메일이면 이메일 문구, 틀린 이메일과 공백이면 공백 문구
    await expectApiError(gateway.contacts.create('customer', person({ company: '', email: 'nope' })), 422, '이메일 형식이 올바르지 않습니다.')
    await expectApiError(gateway.contacts.create('customer', person({ company: '', phone: '12-34' })), 422, '전화번호 형식이 올바르지 않습니다.')
    await expectApiError(gateway.contacts.create('customer', person({ company: '', name: '홍 길동' })), 422, '공백은 입력할 수 없습니다.')
  })

  // 길이 한도와 NUL 문자는 서버와 같이 거절한다
  it('rejects values over the length limits and NUL characters', async () => {
    // given: admin으로 로그인한 Fake
    const { gateway } = await mockAs('root')
    // when·then: 한도 길이는 되고 한도를 넘거나 NUL이 있으면 422 문구다
    await gateway.contacts.create('customer', person({ company: 'a'.repeat(200), name: 'b'.repeat(100), title: 'c'.repeat(100), email: null }))
    await expectApiError(gateway.contacts.create('customer', person({ company: 'a'.repeat(201) })), 422, '회사명은(는) 200자를 넘을 수 없습니다')
    await expectApiError(gateway.contacts.create('customer', person({ name: 'b'.repeat(101) })), 422, '담당자명은(는) 100자를 넘을 수 없습니다')
    await expectApiError(gateway.contacts.create('customer', person({ title: 'c'.repeat(101) })), 422, '직급은(는) 100자를 넘을 수 없습니다')
    await expectApiError(gateway.contacts.create('customer', person({ company: 'a\u0000b' })), 422, '회사명에는 NUL 문자를 쓸 수 없습니다')
  })

  // 목록 기본 limit은 50이고 키워드에 NUL이 있으면 422다
  it('uses a default page size of 50 and rejects NUL in the keyword', async () => {
    // given: admin으로 로그인한 Fake
    const { gateway } = await mockAs('root')
    // when: 조건 없이 읽고, NUL이 든 키워드로 읽는다
    const page = await gateway.contacts.list({})
    // then: 기본 limit 50, NUL 키워드는 422다
    expect(page.limit).toBe(50)
    await expectApiError(gateway.contacts.list({ keyword: 'a\u0000b' }), 422, '검색어에는 NUL 문자를 쓸 수 없습니다')
  })

  // 키워드 길이는 앞뒤 공백을 지우기 전 값으로 세고 위반 문구에 마침표가 없다
  // (번호 없는 Fake 자체 테스트: 서버 request-validation 문구·길이 기준과 일치)
  it('counts keyword length before trimming and uses the server message without a period', async () => {
    // given: admin으로 로그인한 Fake
    const { gateway } = await mockAs('root')
    // when: 공백 포함 101자와 공백 제외 100자 키워드로 읽는다
    const padded = ` ${'a'.repeat(100)}`
    // then: 공백 포함 101자는 마침표 없는 서버 문구로 422, 공백 없는 100자는 통과한다
    await expectApiError(gateway.contacts.list({ keyword: padded }), 422, '요청 형식이 올바르지 않습니다')
    expect((await gateway.contacts.list({ keyword: 'a'.repeat(100) })).total).toBe(0)
  })
})
