/** 연락처(DL-13, AC-17~22) 계약. */

import { describe, expect, it } from 'vitest'
import type { ContactInput } from '../../shared/model/types'
import { expectRejects, unique, type MakeGateway } from './support'

function person(company: string, over: Partial<ContactInput> = {}): ContactInput {
  return { company, name: '홍길동', title: '', email: null, phone: null, ...over }
}

export function contactsContract(make: MakeGateway): void {
  describe('contacts 계약', () => {
    it('registers, finds by keyword with a Deal count of 0, updates and deletes', async () => {
      const { contacts } = await make('admin')
      const company = unique('co')

      const created = await contacts.create('customer', person(company, { title: '팀장', email: 'hong@neoine.test', phone: '010-1234-5678' }))

      expect(created).toMatchObject({ kind: 'customer', company, name: '홍길동', title: '팀장', email: 'hong@neoine.test', phone: '010-1234-5678' })
      const page = await contacts.list({ kind: 'customer', keyword: company })
      expect(page.total).toBe(1)
      expect(page.items[0]).toMatchObject({ id: created.id, dealCount: 0 })
      const updated = await contacts.update(created.id, person(company, { name: '김철수', title: '' }))
      expect(updated).toMatchObject({ id: created.id, kind: 'customer', name: '김철수', title: '' })
      await contacts.remove(created.id)
      expect((await contacts.list({ keyword: company })).total).toBe(0)
    })

    it('shows the company in the lookups for every role', async () => {
      const company = unique('lookup')
      const created = await (await make('admin')).contacts.create('partner', person(company))

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
    ] as const)('rejects %j with 422', async (over, message) => {
      const { contacts } = await make('admin')

      await expectRejects(contacts.create('customer', person(unique('v'), over)), 422, message)
    })

    it('rejects a blank company with 422', async () => {
      const { contacts } = await make('admin')

      await expectRejects(contacts.create('customer', person('')), 422, '회사명을 입력하세요.')
    })

    it('refuses the same person twice in a kind with 409, and allows the other kind', async () => {
      const { contacts } = await make('admin')
      const company = unique('same')
      const first = await contacts.create('customer', person(company, { email: 'a@neoine.test' }))

      await expectRejects(contacts.create('customer', person(company.toUpperCase(), { email: 'A@neoine.test' })), 409, '이미 등록된 연락처입니다.')
      const partner = await contacts.create('partner', person(company, { email: 'a@neoine.test' }))
      expect(partner.kind).toBe('partner')

      await contacts.remove(first.id)
      await contacts.remove(partner.id)
    })

    it('refuses an update that turns the contact into another existing person with 409', async () => {
      const { contacts } = await make('admin')
      const company = unique('clash')
      const a = await contacts.create('customer', person(company, { name: '가나다' }))
      const b = await contacts.create('customer', person(company, { name: '라마바' }))

      await expectRejects(contacts.update(b.id, person(company, { name: '가나다' })), 409, '이미 등록된 연락처입니다.')

      await contacts.remove(a.id)
      await contacts.remove(b.id)
    })

    it.each(['sales', 'user'] as const)('refuses %s the list and every change with 403', async (role) => {
      const { contacts } = await make(role)

      await expectRejects(contacts.list({}), 403)
      await expectRejects(contacts.create('customer', person(unique('x'))), 403)
      await expectRejects(contacts.update('x', person('x')), 403)
      await expectRejects(contacts.remove('x'), 403)
    })

    it('pages the list with the total of the filter', async () => {
      const { contacts } = await make('admin')
      const company = unique('page')
      const made = []
      for (const name of ['가가', '나나', '다다']) made.push(await contacts.create('customer', person(company, { name })))

      const first = await contacts.list({ keyword: company, offset: 0, limit: 2 })
      const second = await contacts.list({ keyword: company, offset: 2, limit: 2 })

      expect(first).toMatchObject({ total: 3, offset: 0, limit: 2 })
      expect(first.items.map((c) => c.name)).toEqual(['가가', '나나'])
      expect(second.items.map((c) => c.name)).toEqual(['다다'])
      for (const c of made) await contacts.remove(c.id)
    })
  })
}
