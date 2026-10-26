/** 서버 시각 계약(시간 기준 서버 통일 AC1). mock과 실제 서버가 같은 모양을 낸다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, type MakeGateway } from './support'

const OFFSET_ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$/

export function timeContract(make: MakeGateway): void {
  describe('time 계약', () => {
    it.each(['admin', 'sales', 'user'] as const)('returns the server now with an offset and its date to %s', async (role) => {
      const { time } = await make(role)

      const result = await time.get()

      expect(Object.keys(result).sort()).toEqual(['now', 'today'])
      expect(result.now).toMatch(OFFSET_ISO)
      expect(result.today).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(result.today).toBe(result.now.slice(0, 10)) // 오늘은 now에 적힌 오프셋의 달력 날짜다
    })

    it('rejects an anonymous caller with 401', async () => {
      const gateway = await make('user')
      await gateway.auth.logout()

      await expectRejects(gateway.time.get(), 401)
    })
  })
}
