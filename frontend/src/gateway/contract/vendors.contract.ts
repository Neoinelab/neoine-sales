/** Vendor 관리(AC-1~5) 계약. Solution 관리는 없다. 호출마다 고유한 이름을 쓰고 만든 것은 스스로 치운다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const DUP_VENDOR = '이미 있는 Vendor 이름입니다.'

export function vendorsContract(make: MakeGateway): void {
  describe('vendors 계약', () => {
    it('lets every role read the list, sorted by lower-case name', async () => {
      const admin = await make('admin')
      const prefix = unique('v')
      const b = await admin.vendors.create(`${prefix}B`)
      const a = await admin.vendors.create(`${prefix}a`)

      for (const role of ['admin', 'sales', 'user'] as const) {
        const { vendors } = await make(role)
        const mine = (await vendors.list()).filter((v) => v.name.toLowerCase().startsWith(prefix))
        expect(mine.map((v) => v.name)).toEqual([`${prefix}a`, `${prefix}B`])
      }
      const cleanup = await make('admin')
      await cleanup.vendors.remove(a.id)
      await cleanup.vendors.remove(b.id)
    })

    it('creates a trimmed vendor with zero usage and no solution list (AC-1)', async () => {
      const { vendors } = await make('admin')
      const name = unique('vendor')

      const created = await vendors.create(`  ${name}  `)

      expect(created).toEqual({ id: created.id, name, usageCount: 0 })
      expect(created).not.toHaveProperty('solutions')
      await vendors.remove(created.id)
    })

    it('has no solution management methods (AC-2)', async () => {
      const { vendors } = await make('admin')

      for (const method of ['createSolution', 'renameSolution', 'removeSolution']) {
        expect(vendors).not.toHaveProperty(method)
      }
    })

    it('refuses writes from sales and user with 403 (AC-3)', async () => {
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))

      for (const role of ['sales', 'user'] as const) {
        const { vendors } = await make(role)
        await expectRejects(vendors.create(unique('x')), 403)
        await expectRejects(vendors.rename(vendor.id, unique('x')), 403)
        await expectRejects(vendors.remove(vendor.id), 403)
      }
      await (await make('admin')).vendors.remove(vendor.id)
    })

    it('validates names: blank and 101 characters (AC-3)', async () => {
      const { vendors } = await make('admin')
      const vendor = await vendors.create(unique('vendor'))

      await expectRejects(vendors.create('   '), 422, 'Vendor 이름을 입력하세요.')
      await expectRejects(vendors.create('v'.repeat(101)), 422, 'Vendor 이름은 100자 이내로 입력하세요.')
      await expectRejects(vendors.rename(vendor.id, ' '), 422, 'Vendor 이름을 입력하세요.')
      await vendors.remove(vendor.id)
    })

    it('rejects duplicate names ignoring case (AC-3)', async () => {
      const { vendors } = await make('admin')
      const name = unique('vendor')
      const first = await vendors.create(name)
      const second = await vendors.create(unique('vendor'))

      await expectRejects(vendors.create(name.toUpperCase()), 409, DUP_VENDOR)
      await expectRejects(vendors.rename(second.id, name.toUpperCase()), 409, DUP_VENDOR)
      await expect(vendors.rename(first.id, name.toUpperCase())).resolves.toMatchObject({ name: name.toUpperCase() })
      await vendors.remove(first.id)
      await vendors.remove(second.id)
    })

    it('treats unknown ids as 404 (AC-4)', async () => {
      const { vendors } = await make('admin')

      await expectRejects(vendors.rename(NO_SUCH_ID, unique('x')), 404)
      await expectRejects(vendors.remove(NO_SUCH_ID), 404)
    })

    it('refuses to delete a vendor a deal uses, with the count, and keeps it (AC-4)', async () => {
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

      await expectRejects(vendors.remove(vendor.id), 409, '사용 중인 Vendor는 삭제할 수 없습니다. (Deal 1건)')

      const listed = (await vendors.list()).find((v) => v.id === vendor.id)
      expect(listed).toMatchObject({ usageCount: 1 })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).vendors.remove(vendor.id)
    })

    it('deletes an unused vendor (AC-4)', async () => {
      const { vendors } = await make('admin')
      const vendor = await vendors.create(unique('vendor'))

      await vendors.remove(vendor.id)

      expect((await vendors.list()).some((v) => v.id === vendor.id)).toBe(false)
    })
  })
}
