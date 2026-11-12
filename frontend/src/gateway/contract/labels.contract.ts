/** BANT Label 계약. */

import { describe, expect, it } from 'vitest'
import { expectRejects, unique, type MakeGateway } from './support'

const DUPLICATE = '같은 구분에 이미 있는 Label 이름입니다.'

export function labelsContract(make: MakeGateway): void {
  describe('labels 계약', () => {
    it('모든 역할이 네 구분의 기본 Label 목록을 볼 수 있다', async () => {
      // when·then: 역할마다 목록을 읽으면 기본 Label이 구분별로 7·6·5·5개이고 만든 사람이 없다
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { labels } = await make(role)
        const defaults = (await labels.list()).filter((l) => l.isDefault)

        expect(['budget', 'authority', 'need', 'timeline'].map((c) => defaults.filter((l) => l.category === c).length)).toEqual([7, 6, 5, 5])
        expect(defaults.every((l) => l.createdBy === null)).toBe(true)
      }
    })

    it('영업이 Label을 만들면 앞뒤 공백이 잘린 기본 아님 Label이 되고 관리자가 삭제할 수 있다', async () => {
      // given: 영업 게이트웨이와 고유한 이름
      const sales = await make('sales')
      const name = unique('label')

      // when: 공백으로 감싼 이름으로 영업이 Label을 만든다
      const created = await sales.labels.create('need', `  ${name}  `)

      // then: 공백이 잘린 기본 아님 Label이고 만든 사람이 있다
      expect(created).toMatchObject({ category: 'need', name, isDefault: false, usageCount: 0 })
      expect(created.createdBy).not.toBeNull()
      // when: 관리자가 삭제한다
      const admin = await make('admin')
      await admin.labels.remove(created.id)
      // then: 목록에서 사라진다
      expect((await admin.labels.list()).some((l) => l.id === created.id)).toBe(false)
    })

    it('user 역할의 Label 생성은 403으로 거절한다', async () => {
      // when·then: user가 Label을 만들면 403이다
      const { labels } = await make('user')

      await expectRejects(labels.create('budget', unique('x')), 403)
    })

    it('공백뿐이거나 너무 긴 이름은 422로 거절한다', async () => {
      // when·then: 공백 이름과 51자 이름은 각각 안내 문구와 함께 422가 된다
      const { labels } = await make('admin')

      await expectRejects(labels.create('budget', '   '), 422, 'Label 이름을 입력하세요.')
      await expectRejects(labels.create('budget', 'x'.repeat(51)), 422, 'Label 이름은 50자 이내로 입력하세요.')
    })

    it('같은 구분의 대소문자 무시 중복은 거절하고 다른 구분의 같은 이름은 허용한다', async () => {
      // given: budget 구분에 이름 하나를 만든다
      const { labels } = await make('admin')
      const name = unique('same')
      const first = await labels.create('budget', name)

      // when: 같은 구분에 대문자 이름으로, 다른 구분에 같은 이름으로 만든다
      await expectRejects(labels.create('budget', name.toUpperCase()), 409, DUPLICATE)
      const other = await labels.create('timeline', name)
      // then: 같은 구분은 409로 거절되고 다른 구분은 만들어진다
      expect(other.category).toBe('timeline')

      await labels.remove(first.id)
      await labels.remove(other.id)
    })

    it('이름을 바꿀 수 있고 같은 구분에 있는 이름으로는 바꿀 수 없다', async () => {
      // given: authority 구분의 Label 두 개
      const { labels } = await make('admin')
      const a = await labels.create('authority', unique('a'))
      const b = await labels.create('authority', unique('b'))

      // when: 새 이름으로 바꾸고, 다른 Label의 이름으로도 바꿔 본다
      const renamed = await labels.rename(a.id, unique('renamed'))
      // then: 새 이름은 같은 id로 바뀌고 중복 이름은 409로 거절된다
      expect(renamed.id).toBe(a.id)
      await expectRejects(labels.rename(b.id, renamed.name.toUpperCase()), 409, DUPLICATE)

      await labels.remove(a.id)
      await labels.remove(b.id)
    })

    it('영업의 이름 변경·삭제는 403으로 거절한다', async () => {
      // given: 관리자가 만든 Label
      const created = await (await make('admin')).labels.create('budget', unique('own'))
      const sales = await make('sales')

      // when·then: 영업이 이름을 바꾸거나 삭제하면 403이다
      await expectRejects(sales.labels.rename(created.id, unique('x')), 403)
      await expectRejects(sales.labels.remove(created.id), 403)

      await (await make('admin')).labels.remove(created.id)
    })
  })
}
