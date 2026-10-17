/** 경고 기준(P3 AC-05~07, AC-14) 계약. mock·HTTP 공통. 저장한 값은 테스트가 끝날 때 14로 되돌린다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, type MakeGateway } from './support'

const RANGE_MESSAGE = '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'

export function alertsContract(make: MakeGateway): void {
  describe('alerts 계약', () => {
    it('lets every role read an integer threshold between 1 and 365', async () => {
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { alerts } = await make(role)
        const settings = await alerts.get()

        expect(Number.isInteger(settings.staleDays)).toBe(true)
        expect(settings.staleDays).toBeGreaterThanOrEqual(1)
        expect(settings.staleDays).toBeLessThanOrEqual(365)
      }
    })

    it('lets the admin save, returns the saver and time, and every role then reads the new value', async () => {
      const admin = await make('admin')

      const saved = await admin.alerts.save(30)

      expect(saved.staleDays).toBe(30)
      expect(saved.updatedAt).not.toBeNull()
      expect(saved.updatedBy).toMatchObject({ role: 'admin' })
      const sales = await make('sales')
      expect((await sales.alerts.get()).staleDays).toBe(30)
      await (await make('admin')).alerts.save(14)
    })

    it('accepts the boundaries 1 and 365', async () => {
      const { alerts } = await make('admin')

      expect((await alerts.save(1)).staleDays).toBe(1)
      expect((await alerts.save(365)).staleDays).toBe(365)
      await alerts.save(14)
    })

    it('refuses sales and user to save with 403 and keeps the value', async () => {
      const before = (await (await make('admin')).alerts.get()).staleDays

      for (const role of ['sales', 'user'] as const) {
        const gateway = await make(role)
        await expectRejects(gateway.alerts.save(before === 99 ? 98 : 99), 403)
      }

      expect((await (await make('admin')).alerts.get()).staleDays).toBe(before)
    })

    it('rejects out-of-range integers with 422 and the range sentence, keeping the stored value', async () => {
      const { alerts } = await make('admin')
      const before = (await alerts.get()).staleDays

      await expectRejects(alerts.save(0), 422, RANGE_MESSAGE)
      await expectRejects(alerts.save(366), 422, RANGE_MESSAGE)
      await expectRejects(alerts.save(-5), 422, RANGE_MESSAGE)

      expect((await alerts.get()).staleDays).toBe(before)
    })

    it('rejects a non-integer with 422', async () => {
      const { alerts } = await make('admin')

      await expectRejects(alerts.save(1.5), 422)
      await expectRejects(alerts.save(Number.NaN), 422)
    })
  })
}
