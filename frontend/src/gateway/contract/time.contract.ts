/** 서버 시각 계약. Fake와 실제 서버가 같은 모양을 낸다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, type MakeGateway } from './support'

const OFFSET_ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$/

export function timeContract(make: MakeGateway): void {
  describe('time 계약', () => {
    // 세 역할 모두 오프셋이 있는 now와 그 날짜 today를 받는다.
    // 테스트 코드: TM-029
    it.each(['admin', 'sales', 'user'] as const)('returns the server now with an offset and its date to %s', async (role) => {
      // given: 역할별로 로그인한 게이트웨이
      const { time } = await make(role)

      // when: 서버 시각을 읽는다
      const result = await time.get()

      // then: 키는 now·today뿐이고 today는 now에 적힌 날짜다
      expect(Object.keys(result).sort()).toEqual(['now', 'today'])
      expect(result.now).toMatch(OFFSET_ISO)
      expect(result.today).toMatch(/^\d{4}-\d{2}-\d{2}$/)
      expect(result.today).toBe(result.now.slice(0, 10)) // 오늘은 now에 적힌 오프셋의 달력 날짜다
    })

    // 로그인하지 않으면 401이다.
    it('rejects an anonymous caller with 401', async () => {
      // given: 로그아웃한 게이트웨이
      const gateway = await make('user')
      await gateway.auth.logout()

      // when·then: 서버 시각 요청은 401
      await expectRejects(gateway.time.get(), 401)
    })
  })
}
