/** 연락처 계약. */

import { describe, expect, it } from 'vitest'
import type { ContactInput } from '../../shared/model/types'
import { expectRejects, unique, type MakeGateway } from './support'

function person(company: string, over: Partial<ContactInput> = {}): ContactInput {
  return { company, name: '홍길동', title: '', email: null, phone: null, ...over }
}

export function contactsContract(make: MakeGateway): void {
  describe('contacts 계약', () => {
    it('연락처를 등록하고 키워드로 찾고(Deal 건수 0) 수정하고 삭제한다', async () => {
      const { contacts } = await make('admin')
      const company = unique('co')

      // when: 고객 연락처를 등록한다
      const created = await contacts.create('customer', person(company, { title: '팀장', email: 'hong@neoine.test', phone: '010-1234-5678' }))

      // then: 입력한 값으로 등록된다
      expect(created).toMatchObject({ kind: 'customer', company, name: '홍길동', title: '팀장', email: 'hong@neoine.test', phone: '010-1234-5678' })
      // when: 회사명 키워드로 목록을 조회한다
      const page = await contacts.list({ kind: 'customer', keyword: company })
      // then: 1건이고 Deal 건수는 0이다
      expect(page.total).toBe(1)
      expect(page.items[0]).toMatchObject({ id: created.id, dealCount: 0 })
      // when: 이름을 바꿔 수정한다
      const updated = await contacts.update(created.id, person(company, { name: '김철수', title: '' }))
      // then: 같은 id로 이름이 바뀐다
      expect(updated).toMatchObject({ id: created.id, kind: 'customer', name: '김철수', title: '' })
      // when: 삭제한다
      await contacts.remove(created.id)
      // then: 키워드 조회 결과가 없다
      expect((await contacts.list({ keyword: company })).total).toBe(0)
    })

    it('모든 역할이 회사 목록과 회사별 연락처 조회에서 회사를 본다', async () => {
      // given: 파트너 연락처 하나
      const company = unique('lookup')
      const created = await (await make('admin')).contacts.create('partner', person(company))

      // when·then: 어느 역할이든 파트너 회사 목록에 있고(대소문자 무시 조회 포함) 고객 회사 목록에는 없다
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { contacts } = await make(role)
        expect(await contacts.companies('partner')).toContain(company)
        expect((await contacts.byCompany('partner', company.toUpperCase())).map((c) => c.id)).toEqual([created.id])
        expect(await contacts.companies('customer')).not.toContain(company)
      }
      await (await make('admin')).contacts.remove(created.id)
    })

    it.each([
      [{ company: 'a b' }, '공백은 입력할 수 없습니다.'],
      [{ name: '홍 길동' }, '공백은 입력할 수 없습니다.'],
      [{ email: 'a b@c.co' }, '공백은 입력할 수 없습니다.'],
      [{ phone: '010 1234 5678' }, '공백은 입력할 수 없습니다.'],
      [{ name: '' }, '담당자명을 입력하세요.'],
      [{ email: 'not-an-email' }, '이메일 형식이 올바르지 않습니다.'],
      [{ phone: '12-34' }, '전화번호 형식이 올바르지 않습니다.'],
    ] as const)('잘못된 입력 %j은(는) 422로 거절한다', async (over, message) => {
      const { contacts } = await make('admin')

      // when·then: 등록하면 해당 문구와 함께 422다
      await expectRejects(contacts.create('customer', person(unique('v'), over)), 422, message)
    })

    it('빈 회사명은 422로 거절한다', async () => {
      const { contacts } = await make('admin')

      // when·then: 회사명이 비면 422와 회사명 문구다
      await expectRejects(contacts.create('customer', person('')), 422, '회사명을 입력하세요.')
    })

    it('같은 종류에 같은 사람을 두 번 등록하면 409이고 다른 종류는 허용한다', async () => {
      const { contacts } = await make('admin')
      const company = unique('same')
      // given: 고객 연락처 하나
      const first = await contacts.create('customer', person(company, { email: 'a@neoine.test' }))

      // when·then: 회사명 대소문자·이메일 대소문자만 달라도 고객으로 또 등록하면 409다
      await expectRejects(contacts.create('customer', person(company.toUpperCase(), { email: 'A@neoine.test' })), 409, '이미 등록된 연락처입니다.')
      // when: 같은 사람을 파트너로 등록한다
      const partner = await contacts.create('partner', person(company, { email: 'a@neoine.test' }))
      // then: 파트너로는 등록된다
      expect(partner.kind).toBe('partner')

      await contacts.remove(first.id)
      await contacts.remove(partner.id)
    })

    it('수정으로 다른 기존 사람과 같아지면 409로 거절한다', async () => {
      // given: 같은 회사의 두 고객 연락처
      const { contacts } = await make('admin')
      const company = unique('clash')
      const a = await contacts.create('customer', person(company, { name: '가나다' }))
      const b = await contacts.create('customer', person(company, { name: '라마바' }))

      // when·then: 한 연락처를 다른 연락처와 같은 이름으로 수정하면 409다
      await expectRejects(contacts.update(b.id, person(company, { name: '가나다' })), 409, '이미 등록된 연락처입니다.')

      await contacts.remove(a.id)
      await contacts.remove(b.id)
    })

    it.each(['sales', 'user'] as const)('%s 역할은 목록과 모든 변경이 403으로 거절된다', async (role) => {
      const { contacts } = await make(role)

      // when·then: 목록·등록·수정·삭제가 모두 403이다
      await expectRejects(contacts.list({}), 403)
      await expectRejects(contacts.create('customer', person(unique('x'))), 403)
      await expectRejects(contacts.update(1, person('x')), 403)
      await expectRejects(contacts.remove(1), 403)
    })

    it('목록은 조건에 맞는 전체 건수와 함께 쪽으로 나눈다', async () => {
      const { contacts } = await make('admin')
      // given: 같은 회사의 연락처 3건
      const company = unique('page')
      const made = []
      for (const name of ['가가', '나나', '다다']) made.push(await contacts.create('customer', person(company, { name })))

      // when: 2건씩 첫 쪽과 둘째 쪽을 조회한다
      const first = await contacts.list({ keyword: company, offset: 0, limit: 2 })
      const second = await contacts.list({ keyword: company, offset: 2, limit: 2 })

      // then: 전체 3건이고 쪽마다 해당 항목만 돌아온다
      expect(first).toMatchObject({ total: 3, offset: 0, limit: 2 })
      expect(first.items.map((c) => c.name)).toEqual(['가가', '나나'])
      expect(second.items.map((c) => c.name)).toEqual(['다다'])
      for (const c of made) await contacts.remove(c.id)
    })
  })
}
