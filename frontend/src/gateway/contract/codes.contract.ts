/** 코드(CM-07) 계약. mock과 HTTP 어댑터가 같은 시나리오·문구를 지켜야 한다. */

import { describe, expect, it } from 'vitest'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const LOCKED_MESSAGE = '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.'

export function codesContract(make: MakeGateway): void {
  describe('codes 계약', () => {
    it('코드를 생성 키와 함께 맨 끝에 추가하고, 쓰지 않는 코드는 삭제한다', async () => {
      // given: 관리자 게이트웨이
      const { codes } = await make('admin')
      const name = unique('stage')

      // when: 코드를 추가한다
      const created = await codes.create({ kind: 'status', name })

      // then: 잠기지 않은 새 코드가 목록 끝에 있고, 삭제하면 목록에서 사라진다
      expect(created).toMatchObject({ kind: 'status', name, locked: false, usageCount: 0 })
      expect(created.key).toMatch(/^[a-z0-9_]+$/)
      const list = await codes.list('status')
      expect(list[list.length - 1]?.id).toBe(created.id)
      await codes.remove(created.id)
      expect((await codes.list('status')).some((c) => c.id === created.id)).toBe(false)
    })

    it('Forecast 코드는 open으로 추가된다', async () => {
      // given: 관리자 게이트웨이
      const { codes } = await make('admin')
      // when: Forecast 코드를 추가한다
      const created = await codes.create({ kind: 'forecast', name: unique('fc') })

      // then: 결과 구분이 open이다
      expect(created.outcome).toBe('open')

      await codes.remove(created.id)
    })

    it('공백뿐인 이름은 422로 거절한다', async () => {
      // given: 관리자 게이트웨이
      const { codes } = await make('admin')

      // when·then: 공백 이름으로 만들면 422 안내 문구로 거절된다
      await expectRejects(codes.create({ kind: 'status', name: '   ' }), 422, '이름을 입력하세요.')
    })

    it('같은 종류에서 대소문자만 다른 이름은 생성·이름 변경 모두 409로 거절한다', async () => {
      // given: 코드 두 개
      const { codes } = await make('admin')
      const name = unique('dup')
      const first = await codes.create({ kind: 'status', name })
      const second = await codes.create({ kind: 'status', name: unique('other') })

      // when·then: 대문자로 바꾼 같은 이름의 생성·이름 변경은 409로 거절된다
      await expectRejects(codes.create({ kind: 'status', name: name.toUpperCase() }), 409, '같은 이름의 코드가 이미 있습니다.')
      await expectRejects(codes.rename(second.id, name.toUpperCase()), 409, '같은 이름의 코드가 이미 있습니다.')

      await codes.remove(first.id)
      await codes.remove(second.id)
    })

    it('이름을 바꿔도 키는 그대로이고 잠긴 코드도 마찬가지다', async () => {
      // given: 관리자 게이트웨이
      const { codes } = await make('admin')
      const created = await codes.create({ kind: 'status', name: unique('before') })
      // when: 일반 코드의 이름을 바꾼다
      const renamed = await codes.rename(created.id, unique('after'))

      // then: id와 키가 그대로다
      expect(renamed.key).toBe(created.key)
      expect(renamed.id).toBe(created.id)

      await codes.remove(created.id)
      const locked = (await codes.list('status')).find((c) => c.locked)
      if (!locked) throw new Error('잠긴 코드가 없습니다.')
      // when: 잠긴 코드를 같은 이름으로 바꾼다
      const same = await codes.rename(locked.id, locked.name)
      // then: 키가 그대로다
      expect(same.key).toBe(locked.key)
    })

    it('id 목록 전체를 보내면 순서를 1부터 다시 매긴다', async () => {
      // given: 새 코드를 만들고 맨 앞으로 옮길 id 목록
      const { codes } = await make('admin')
      const created = await codes.create({ kind: 'status', name: unique('first') })
      const before = await codes.list('status')
      const moved = [created.id, ...before.filter((c) => c.id !== created.id).map((c) => c.id)]

      // when: 전체 id 목록으로 순서를 바꾼다
      const after = await codes.reorder('status', moved)

      // then: 보낸 순서대로이고 순서 값이 1부터 매겨진다
      expect(after.map((c) => c.id)).toEqual(moved)
      expect(after.map((c) => c.order)).toEqual(moved.map((_, i) => i + 1))
      await codes.remove(created.id)
    })

    it('id가 빠졌거나 겹친 목록은 422로 거절한다', async () => {
      // given: 현재 코드 id 목록
      const { codes } = await make('admin')
      const ids = (await codes.list('status')).map((c) => c.id)

      // when·then: 하나가 빠진 목록과 하나가 겹친 목록은 순서 목록 오류 422가 된다
      await expectRejects(codes.reorder('status', ids.slice(1)), 422, '순서 목록이 올바르지 않습니다.')
      await expectRejects(codes.reorder('status', [...ids, ids[0] ?? NO_SUCH_ID]), 422, '순서 목록이 올바르지 않습니다.')
    })

    it('잠긴 코드의 삭제는 409로 거절한다', async () => {
      // given: 시스템과 연결된 won 코드
      const { codes } = await make('admin')
      const locked = (await codes.list('forecast')).find((c) => c.key === 'won')
      if (!locked) throw new Error('won이 없습니다.')

      // when·then: 삭제하면 잠금 안내 문구로 409가 된다
      await expectRejects(codes.remove(locked.id), 409, LOCKED_MESSAGE)
    })

    it('모든 역할이 코드를 읽을 수 있다', async () => {
      // when·then: 역할마다 전체 코드를 읽으면 Status가 있고 Forecast에 won이 있다
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { codes } = await make(role)
        const set = await codes.all()
        expect(set.statuses.length).toBeGreaterThan(0)
        expect(set.forecasts.map((c) => c.key)).toContain('won')
      }
    })

    it.each(['sales', 'user'] as const)('%s 역할에는 사용 현황 목록과 모든 변경을 403으로 거절한다', async (role) => {
      // when·then: 목록·생성·이름 변경·순서 변경·삭제가 모두 403이 된다
      const { codes } = await make(role)

      await expectRejects(codes.list('status'), 403)
      await expectRejects(codes.create({ kind: 'status', name: unique('x') }), 403)
      await expectRejects(codes.rename(1, 'y'), 403)
      await expectRejects(codes.reorder('status', []), 403)
      await expectRejects(codes.remove(1), 403)
    })
  })
}
