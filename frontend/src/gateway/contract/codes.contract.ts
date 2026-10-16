/** 코드(CM-07, AC-03~09) 계약. mock과 HTTP 어댑터가 같은 시나리오·문구를 지켜야 한다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, unique, type MakeGateway } from './support'

const LOCKED_MESSAGE = '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.'

export function codesContract(make: MakeGateway): void {
  describe('codes 계약', () => {
    it('adds a code at the end with a generated key, and removes an unused one', async () => {
      const { codes } = await make('admin')
      const name = unique('stage')

      const created = await codes.create({ kind: 'status', name })

      expect(created).toMatchObject({ kind: 'status', name, locked: false, usageCount: 0 })
      expect(created.key).toMatch(/^[a-z0-9_]+$/)
      const list = await codes.list('status')
      expect(list[list.length - 1]?.id).toBe(created.id)
      await codes.remove(created.id)
      expect((await codes.list('status')).some((c) => c.id === created.id)).toBe(false)
    })

    it('adds a forecast code as open', async () => {
      const { codes } = await make('admin')
      const created = await codes.create({ kind: 'forecast', name: unique('fc') })

      expect(created.outcome).toBe('open')

      await codes.remove(created.id)
    })

    it('rejects a blank name with 422', async () => {
      const { codes } = await make('admin')

      await expectRejects(codes.create({ kind: 'status', name: '   ' }), 422, '이름을 입력하세요.')
    })

    it('rejects a same-kind duplicate that differs only by case, on create and on rename', async () => {
      const { codes } = await make('admin')
      const name = unique('dup')
      const first = await codes.create({ kind: 'status', name })
      const second = await codes.create({ kind: 'status', name: unique('other') })

      await expectRejects(codes.create({ kind: 'status', name: name.toUpperCase() }), 409, '같은 이름의 코드가 이미 있습니다.')
      await expectRejects(codes.rename(second.id, name.toUpperCase()), 409, '같은 이름의 코드가 이미 있습니다.')

      await codes.remove(first.id)
      await codes.remove(second.id)
    })

    it('renames without changing the key, locked codes included', async () => {
      const { codes } = await make('admin')
      const created = await codes.create({ kind: 'status', name: unique('before') })
      const renamed = await codes.rename(created.id, unique('after'))

      expect(renamed.key).toBe(created.key)
      expect(renamed.id).toBe(created.id)

      await codes.remove(created.id)
      const locked = (await codes.list('status')).find((c) => c.locked)
      if (!locked) throw new Error('잠긴 코드가 없습니다.')
      const same = await codes.rename(locked.id, locked.name)
      expect(same.key).toBe(locked.key)
    })

    it('renumbers the order from 1 when the whole id list is sent', async () => {
      const { codes } = await make('admin')
      const created = await codes.create({ kind: 'status', name: unique('first') })
      const before = await codes.list('status')
      const moved = [created.id, ...before.filter((c) => c.id !== created.id).map((c) => c.id)]

      const after = await codes.reorder('status', moved)

      expect(after.map((c) => c.id)).toEqual(moved)
      expect(after.map((c) => c.order)).toEqual(moved.map((_, i) => i + 1))
      await codes.remove(created.id)
    })

    it('rejects an id list that misses an id', async () => {
      const { codes } = await make('admin')
      const ids = (await codes.list('status')).map((c) => c.id)

      await expectRejects(codes.reorder('status', ids.slice(1)), 422, '순서 목록이 올바르지 않습니다.')
      await expectRejects(codes.reorder('status', [...ids, ids[0] ?? '']), 422, '순서 목록이 올바르지 않습니다.')
    })

    it('refuses to delete a locked code with 409', async () => {
      const { codes } = await make('admin')
      const locked = (await codes.list('forecast')).find((c) => c.key === 'won')
      if (!locked) throw new Error('won이 없습니다.')

      await expectRejects(codes.remove(locked.id), 409, LOCKED_MESSAGE)
    })

    it('lets every role read the codes', async () => {
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { codes } = await make(role)
        const set = await codes.all()
        expect(set.statuses.length).toBeGreaterThan(0)
        expect(set.forecasts.map((c) => c.key)).toContain('won')
      }
    })

    it.each(['sales', 'user'] as const)('refuses %s the usage list and every change with 403', async (role) => {
      const { codes } = await make(role)

      await expectRejects(codes.list('status'), 403)
      await expectRejects(codes.create({ kind: 'status', name: unique('x') }), 403)
      await expectRejects(codes.rename('x', 'y'), 403)
      await expectRejects(codes.reorder('status', []), 403)
      await expectRejects(codes.remove('x'), 403)
    })
  })
}
