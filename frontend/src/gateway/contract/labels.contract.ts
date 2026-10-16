/** BANT Label(AC-10~14) 계약. */

import { describe, expect, it } from 'vitest'
import { expectRejects, unique, type MakeGateway } from './support'

const DUPLICATE = '같은 구분에 이미 있는 Label 이름입니다.'

export function labelsContract(make: MakeGateway): void {
  describe('labels 계약', () => {
    it('lists the default labels of all four categories for every role', async () => {
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { labels } = await make(role)
        const defaults = (await labels.list()).filter((l) => l.isDefault)

        expect(['budget', 'authority', 'need', 'timeline'].map((c) => defaults.filter((l) => l.category === c).length)).toEqual([7, 6, 5, 5])
        expect(defaults.every((l) => l.createdBy === null)).toBe(true)
      }
    })

    it('lets sales create a label, trimmed and not default, and the admin remove it', async () => {
      const sales = await make('sales')
      const name = unique('label')

      const created = await sales.labels.create('need', `  ${name}  `)

      expect(created).toMatchObject({ category: 'need', name, isDefault: false, usageCount: 0 })
      expect(created.createdBy).not.toBeNull()
      const admin = await make('admin')
      await admin.labels.remove(created.id)
      expect((await admin.labels.list()).some((l) => l.id === created.id)).toBe(false)
    })

    it('refuses the user role to create with 403', async () => {
      const { labels } = await make('user')

      await expectRejects(labels.create('budget', unique('x')), 403)
    })

    it('rejects blank and over-long names with 422', async () => {
      const { labels } = await make('admin')

      await expectRejects(labels.create('budget', '   '), 422, 'Label 이름을 입력하세요.')
      await expectRejects(labels.create('budget', 'x'.repeat(51)), 422, 'Label 이름은 50자 이내로 입력하세요.')
    })

    it('rejects a same-category duplicate ignoring case, allows the same name in another category', async () => {
      const { labels } = await make('admin')
      const name = unique('same')
      const first = await labels.create('budget', name)

      await expectRejects(labels.create('budget', name.toUpperCase()), 409, DUPLICATE)
      const other = await labels.create('timeline', name)
      expect(other.category).toBe('timeline')

      await labels.remove(first.id)
      await labels.remove(other.id)
    })

    it('renames, and refuses a rename onto an existing name in the category', async () => {
      const { labels } = await make('admin')
      const a = await labels.create('authority', unique('a'))
      const b = await labels.create('authority', unique('b'))

      const renamed = await labels.rename(a.id, unique('renamed'))
      expect(renamed.id).toBe(a.id)
      await expectRejects(labels.rename(b.id, renamed.name.toUpperCase()), 409, DUPLICATE)

      await labels.remove(a.id)
      await labels.remove(b.id)
    })

    it('refuses sales to rename or delete with 403', async () => {
      const created = await (await make('admin')).labels.create('budget', unique('own'))
      const sales = await make('sales')

      await expectRejects(sales.labels.rename(created.id, unique('x')), 403)
      await expectRejects(sales.labels.remove(created.id), 403)

      await (await make('admin')).labels.remove(created.id)
    })
  })
}
