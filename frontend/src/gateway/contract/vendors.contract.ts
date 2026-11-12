/** Vendor 관리 계약. Solution 관리는 없다. 호출마다 고유한 이름을 쓰고 만든 것은 스스로 치운다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const DUP_VENDOR = '이미 있는 Vendor 이름입니다.'

export function vendorsContract(make: MakeGateway): void {
  describe('vendors 계약', () => {
    it('모든 역할이 소문자 이름순으로 정렬된 목록을 읽는다', async () => {
      const admin = await make('admin')
      const prefix = unique('v')
      // given: 대소문자가 섞인 이름의 Vendor 둘
      const b = await admin.vendors.create(`${prefix}B`)
      const a = await admin.vendors.create(`${prefix}a`)

      // when: 역할마다 목록을 읽는다
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { vendors } = await make(role)
        const mine = (await vendors.list()).filter((v) => v.name.toLowerCase().startsWith(prefix))
        // then: 소문자 이름 기준 순서로 보인다
        expect(mine.map((v) => v.name)).toEqual([`${prefix}a`, `${prefix}B`])
      }
      const cleanup = await make('admin')
      await cleanup.vendors.remove(a.id)
      await cleanup.vendors.remove(b.id)
    })

    it('이름 앞뒤 공백을 지워 등록하고 사용 0건이며 Solution 목록은 없다', async () => {
      const { vendors } = await make('admin')
      const name = unique('vendor')

      // when: 앞뒤 공백이 있는 이름으로 등록한다
      const created = await vendors.create(`  ${name}  `)

      // then: 공백이 지워진 이름, 사용 0건이고 solutions 속성은 없다
      expect(created).toEqual({ id: created.id, name, usageCount: 0 })
      expect(created).not.toHaveProperty('solutions')
      await vendors.remove(created.id)
    })

    it('Solution 관리 메서드는 없다', async () => {
      const { vendors } = await make('admin')

      // when·then: Solution 생성·수정·삭제 메서드가 게이트웨이에 없다
      for (const method of ['createSolution', 'renameSolution', 'removeSolution']) {
        expect(vendors).not.toHaveProperty(method)
      }
    })

    it('영업과 조회자의 쓰기는 403으로 거절한다', async () => {
      const admin = await make('admin')
      // given: admin이 등록한 Vendor 하나
      const vendor = await admin.vendors.create(unique('vendor'))

      // when·then: 영업·조회자가 등록·이름 변경·삭제하면 모두 403이다
      for (const role of ['sales', 'user'] as const) {
        const { vendors } = await make(role)
        await expectRejects(vendors.create(unique('x')), 403)
        await expectRejects(vendors.rename(vendor.id, unique('x')), 403)
        await expectRejects(vendors.remove(vendor.id), 403)
      }
      await (await make('admin')).vendors.remove(vendor.id)
    })

    it('이름이 비었거나 101자면 422로 거절한다', async () => {
      const { vendors } = await make('admin')
      // given: Vendor 하나
      const vendor = await vendors.create(unique('vendor'))

      // when·then: 공백만·101자 등록과 공백 이름 변경이 각 문구와 함께 422다
      await expectRejects(vendors.create('   '), 422, 'Vendor 이름을 입력하세요.')
      await expectRejects(vendors.create('v'.repeat(101)), 422, 'Vendor 이름은 100자 이내로 입력하세요.')
      await expectRejects(vendors.rename(vendor.id, ' '), 422, 'Vendor 이름을 입력하세요.')
      await vendors.remove(vendor.id)
    })

    it('대소문자만 다른 중복 이름은 409로 거절한다', async () => {
      // given: Vendor 둘
      const { vendors } = await make('admin')
      const name = unique('vendor')
      const first = await vendors.create(name)
      const second = await vendors.create(unique('vendor'))

      // when·then: 대소문자만 다른 이름의 등록·다른 Vendor 이름 변경은 409이고, 자기 이름의 대소문자 변경은 허용된다
      await expectRejects(vendors.create(name.toUpperCase()), 409, DUP_VENDOR)
      await expectRejects(vendors.rename(second.id, name.toUpperCase()), 409, DUP_VENDOR)
      await expect(vendors.rename(first.id, name.toUpperCase())).resolves.toMatchObject({ name: name.toUpperCase() })
      await vendors.remove(first.id)
      await vendors.remove(second.id)
    })

    it('없는 id는 404로 처리한다', async () => {
      const { vendors } = await make('admin')

      // when·then: 없는 id의 이름 변경과 삭제는 404다
      await expectRejects(vendors.rename(NO_SUCH_ID, unique('x')), 404)
      await expectRejects(vendors.remove(NO_SUCH_ID), 404)
    })

    it('Deal이 쓰는 Vendor는 건수와 함께 삭제를 거절하고 유지한다', async () => {
      // given: 영업이 만든 Deal이 쓰는 Vendor
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await sales.deals.create({
        name: unique('deal'),
        ownerId: me.id,
        vendorId: vendor.id,
        solution: 'ITDR',
        users: 100,
        statusKey: 'prospecting',
        forecastKey: 'pipeline',
        revenueAmount: 1_000_000,
        revenueDate: '2027-02-15',
        customer: { contactId: null, company: unique('co'), name: unique('nm'), title: '', email: null, phone: null },
        partner: null,
        quote: { submitted: null, submittedDate: null },
        poc: { state: null, completedDate: null },
        procurement: '',
        bant: { budget: null, authority: null, need: null, timeline: null },
      })
      const { vendors } = await make('admin')

      // when·then: admin이 삭제하면 사용 건수와 함께 409다
      await expectRejects(vendors.remove(vendor.id), 409, '사용 중인 Vendor는 삭제할 수 없습니다. (Deal 1건)')

      // then: Vendor가 그대로 있고 사용 1건으로 보인다 (끝에 정리한다)
      const listed = (await vendors.list()).find((v) => v.id === vendor.id)
      expect(listed).toMatchObject({ usageCount: 1 })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).vendors.remove(vendor.id)
    })

    it('쓰이지 않는 Vendor는 삭제한다', async () => {
      const { vendors } = await make('admin')
      // given: 쓰이지 않는 Vendor
      const vendor = await vendors.create(unique('vendor'))

      // when: 삭제한다
      await vendors.remove(vendor.id)

      // then: 목록에서 사라진다
      expect((await vendors.list()).some((v) => v.id === vendor.id)).toBe(false)
    })
  })
}
