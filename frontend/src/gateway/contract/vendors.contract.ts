/** Vendor·Solution 관리(AC-1~7) 계약. 호출마다 고유한 이름을 쓰고 만든 것은 스스로 치운다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const DUP_VENDOR = '이미 있는 Vendor 이름입니다.'
const DUP_SOLUTION = '이 Vendor에 이미 있는 Solution 이름입니다.'

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

    it('creates a trimmed vendor with zero usage and an empty solution list (AC-1)', async () => {
      const { vendors } = await make('admin')
      const name = unique('vendor')

      const created = await vendors.create(`  ${name}  `)

      expect(created).toMatchObject({ name, usageCount: 0, solutions: [] })
      await vendors.remove(created.id)
    })

    it('refuses writes from sales and user with 403 (AC-7)', async () => {
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))
      const solution = await admin.vendors.createSolution(vendor.id, unique('solution'))

      for (const role of ['sales', 'user'] as const) {
        const { vendors } = await make(role)
        await expectRejects(vendors.create(unique('x')), 403)
        await expectRejects(vendors.rename(vendor.id, unique('x')), 403)
        await expectRejects(vendors.remove(vendor.id), 403)
        await expectRejects(vendors.createSolution(vendor.id, unique('x')), 403)
        await expectRejects(vendors.renameSolution(vendor.id, solution.id, unique('x')), 403)
        await expectRejects(vendors.removeSolution(vendor.id, solution.id), 403)
      }
      await (await make('admin')).vendors.remove(vendor.id)
    })

    it('validates names: blank, 101 and 201 characters (AC-4)', async () => {
      const { vendors } = await make('admin')
      const vendor = await vendors.create(unique('vendor'))

      await expectRejects(vendors.create('   '), 422, 'Vendor 이름을 입력하세요.')
      await expectRejects(vendors.create('v'.repeat(101)), 422, 'Vendor 이름은 100자 이내로 입력하세요.')
      await expectRejects(vendors.rename(vendor.id, ' '), 422, 'Vendor 이름을 입력하세요.')
      await expectRejects(vendors.createSolution(vendor.id, ' '), 422, 'Solution 이름을 입력하세요.')
      await expectRejects(vendors.createSolution(vendor.id, 's'.repeat(201)), 422, 'Solution 이름은 200자 이내로 입력하세요.')
      await vendors.remove(vendor.id)
    })

    it('rejects duplicate names ignoring case, per vendor for solutions (AC-5)', async () => {
      const { vendors } = await make('admin')
      const name = unique('vendor')
      const first = await vendors.create(name)
      const second = await vendors.create(unique('vendor'))
      const solutionName = unique('solution')
      const solution = await vendors.createSolution(first.id, solutionName)

      await expectRejects(vendors.create(name.toUpperCase()), 409, DUP_VENDOR)
      await expectRejects(vendors.rename(second.id, name.toUpperCase()), 409, DUP_VENDOR)
      await expectRejects(vendors.createSolution(first.id, solutionName.toUpperCase()), 409, DUP_SOLUTION)
      const other = await vendors.createSolution(second.id, solutionName)
      expect(other.name).toBe(solutionName)
      await expect(vendors.renameSolution(first.id, solution.id, solutionName.toUpperCase())).resolves.toMatchObject({ name: solutionName.toUpperCase() })
      await vendors.remove(first.id)
      await vendors.remove(second.id)
    })

    it('treats a solution outside the path vendor and unknown ids as 404 (AC-3, AC-6)', async () => {
      const { vendors } = await make('admin')
      const one = await vendors.create(unique('vendor'))
      const two = await vendors.create(unique('vendor'))
      const solution = await vendors.createSolution(one.id, unique('solution'))

      await expectRejects(vendors.renameSolution(two.id, solution.id, unique('x')), 404)
      await expectRejects(vendors.removeSolution(two.id, solution.id), 404)
      await expectRejects(vendors.createSolution(NO_SUCH_ID, unique('x')), 404)
      await expectRejects(vendors.remove(NO_SUCH_ID), 404)
      await vendors.remove(one.id)
      await vendors.remove(two.id)
    })

    it('refuses to delete what a deal uses, with the count, and keeps it (AC-6)', async () => {
      const admin = await make('admin')
      const vendor = await admin.vendors.create(unique('vendor'))
      const solution = await admin.vendors.createSolution(vendor.id, unique('solution'))
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await sales.deals.create({
        name: unique('deal'),
        ownerId: me.id,
        vendorId: vendor.id,
        solutionId: solution.id,
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

      await expectRejects(vendors.removeSolution(vendor.id, solution.id), 409, '사용 중인 Solution은 삭제할 수 없습니다. (Deal 1건)')
      await expectRejects(vendors.remove(vendor.id), 409, '사용 중인 Vendor는 삭제할 수 없습니다. (Deal 1건)')

      const listed = (await vendors.list()).find((v) => v.id === vendor.id)
      expect(listed).toMatchObject({ usageCount: 1 })
      expect(listed?.solutions[0]).toMatchObject({ id: solution.id, usageCount: 1 })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).vendors.remove(vendor.id)
    })

    it('deletes an unused vendor together with its solutions (AC-6)', async () => {
      const { vendors } = await make('admin')
      const vendor = await vendors.create(unique('vendor'))
      await vendors.createSolution(vendor.id, unique('solution'))
      await vendors.createSolution(vendor.id, unique('solution'))

      await vendors.remove(vendor.id)

      expect((await vendors.list()).some((v) => v.id === vendor.id)).toBe(false)
    })
  })
}
