/** 경고 기준 계약. mock·HTTP 공통. 저장한 값은 테스트가 끝날 때 14로 되돌린다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, type MakeGateway } from './support'

const RANGE_MESSAGE = '미업데이트 기준은 1~365일 사이의 정수로 입력하세요.'

export function alertsContract(make: MakeGateway): void {
  describe('alerts 계약', () => {
    it('모든 역할이 1~365 사이 정수 기준을 읽는다', async () => {
      for (const role of ['admin', 'sales', 'user'] as const) {
        // when: 역할마다 경고 기준을 읽는다
        const { alerts } = await make(role)
        const settings = await alerts.get()

        // then: 1 이상 365 이하의 정수다
        expect(Number.isInteger(settings.staleDays)).toBe(true)
        expect(settings.staleDays).toBeGreaterThanOrEqual(1)
        expect(settings.staleDays).toBeLessThanOrEqual(365)
      }
    })

    it('admin이 저장하면 저장자·시각을 돌려주고 모든 역할이 새 값을 읽는다', async () => {
      const admin = await make('admin')

      // when: admin이 30일로 저장한다
      const saved = await admin.alerts.save(30)

      // then: 값과 저장자·시각이 돌아오고 영업도 30을 읽는다 (끝에 14로 되돌린다)
      expect(saved.staleDays).toBe(30)
      expect(saved.updatedAt).not.toBeNull()
      expect(saved.updatedBy).toMatchObject({ role: 'admin' })
      const sales = await make('sales')
      expect((await sales.alerts.get()).staleDays).toBe(30)
      await (await make('admin')).alerts.save(14)
    })

    it('경계값 1과 365를 받아들인다', async () => {
      const { alerts } = await make('admin')

      // when: 경계값 1과 365로 각각 저장한다
      const low = await alerts.save(1)
      const high = await alerts.save(365)

      // then: 각각 그대로 저장된다 (끝에 14로 되돌린다)
      expect(low.staleDays).toBe(1)
      expect(high.staleDays).toBe(365)
      await alerts.save(14)
    })

    it('영업과 조회자의 저장은 403으로 거절하고 값을 유지한다', async () => {
      // given: 현재 저장된 기준
      const before = (await (await make('admin')).alerts.get()).staleDays

      // when·then: 영업·조회자가 저장하면 403이다
      for (const role of ['sales', 'user'] as const) {
        const gateway = await make(role)
        await expectRejects(gateway.alerts.save(before === 99 ? 98 : 99), 403)
      }

      // then: 저장된 값이 그대로다
      expect((await (await make('admin')).alerts.get()).staleDays).toBe(before)
    })

    it('범위 밖 정수는 422와 범위 문구로 거절하고 값을 유지한다', async () => {
      // given: 현재 저장된 기준
      const { alerts } = await make('admin')
      const before = (await alerts.get()).staleDays

      // when·then: 0·366·-5는 범위 문구와 함께 422다
      await expectRejects(alerts.save(0), 422, RANGE_MESSAGE)
      await expectRejects(alerts.save(366), 422, RANGE_MESSAGE)
      await expectRejects(alerts.save(-5), 422, RANGE_MESSAGE)

      // then: 저장된 값이 그대로다
      expect((await alerts.get()).staleDays).toBe(before)
    })

    it('정수가 아닌 값은 422로 거절한다', async () => {
      const { alerts } = await make('admin')
// when·then: 1.5와 NaN은 422다

      await expectRejects(alerts.save(1.5), 422)
      await expectRejects(alerts.save(Number.NaN), 422)
    })
  })
}
