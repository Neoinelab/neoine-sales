/**
 * Comment 계약(CM). mock과 실제 서버가 같은 규칙·문구·판정 순서를 따라야 한다.
 * 호출마다 고유한 Deal을 만들고 스스로 지운다. Owner는 sales(자기 Deal), 남의 Comment는 admin이 쓴다
 * (mock은 세션이 하나라 마지막으로 만든 역할이 유효하므로 역할을 바꾸면 `make`를 다시 부른다).
 */

import { describe, expect, it } from 'vitest'
import { action, newDeal } from './actions.contract'
import { expectRejects, NO_SUCH_ID, type MakeGateway } from './support'

const NUL = 'Comment에는 NUL 문자를 쓸 수 없습니다'
const EMPTY = 'Comment를 입력하세요.'
const NO_ACTION = '선택한 Action이 이 Deal에 없습니다.'
const READ_ONLY = '이 작업을 할 권한이 없습니다(읽기 전용 계정)'

export function commentsContract(make: MakeGateway): void {
  describe('comments 계약', () => {
    // Deal Comment와 Action Comment를 만들면 최근순으로 읽히고 Action Comment는 연결 Action 요약을 가진다.
    // 테스트 코드: CM-082
    it('lists deal and action comments recent first with the linked action summary', async () => {
      // given: Action이 있는 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const act = await sales.actions.create(deal.code, action({ progress: '킥오프 미팅', nextAction: '문서 전달' }))

      // when: Deal Comment와 Action Comment를 차례로 만들고 읽는다
      const first = await sales.comments.create(deal.code, { body: '  예산 회의 예정  ' })
      const second = await sales.comments.create(deal.code, { body: '자료 전달\n2차 예정', actionId: act.id })
      const all = await sales.comments.list(deal.code)
      const only = await sales.comments.list(deal.code, { actionId: act.id })

      // then: 본문은 앞뒤 공백만 지워지고 최근 것이 먼저이며 연결 Action 요약은 현재 값이다
      expect(first).toMatchObject({ body: '예산 회의 예정', actionId: null, action: null })
      expect(all.map((c) => c.id)).toEqual([second.id, first.id])
      expect(all[0]).toMatchObject({
        body: '자료 전달\n2차 예정',
        actionId: act.id,
        action: { id: act.id, actedOn: act.actedOn, progress: '킥오프 미팅', nextAction: '문서 전달' },
      })
      expect(only.map((c) => c.id)).toEqual([second.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 본문 NUL → 빈 값 → 다른 Deal의 Action 순서로 422이고 아무것도 저장되지 않는다. user는 403이다.
    // 테스트 코드: CM-082
    it('refuses a NUL, a blank body and a foreign action with 422 and refuses a read-only user with 403', async () => {
      // given: Deal 둘과 다른 Deal의 Action
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const other = await newDeal(sales)
      const foreign = await sales.actions.create(other.code, action())

      // when·then: NUL, 공백뿐, 다른 Deal의 Action, 없는 Action은 서버 문구의 422다
      await expectRejects(sales.comments.create(deal.code, { body: '가\u0000나' }), 422, NUL)
      await expectRejects(sales.comments.create(deal.code, { body: '   ' }), 422, EMPTY)
      await expectRejects(sales.comments.create(deal.code, { body: 'x', actionId: foreign.id }), 422, NO_ACTION)
      await expectRejects(sales.comments.create(deal.code, { body: 'x', actionId: NO_SUCH_ID }), 422, NO_ACTION)
      // then: 아무것도 저장되지 않았다
      expect(await sales.comments.list(deal.code)).toEqual([])
      // when·then: user는 읽기 전용 403이고 읽기는 된다
      const user = await make('user')
      await expectRejects(user.comments.create(deal.code, { body: 'x' }), 403, READ_ONLY)
      expect(await user.comments.list(deal.code)).toEqual([])
      await (await make('admin')).deals.remove(deal.code, deal.code)
      await (await make('admin')).deals.remove(other.code, other.code)
    })

    // Owner가 쓰면 읽음, 다른 사람(admin)이 쓰면 읽지 않음이고 읽지 않은 수는 Deal·Action별로 센다.
    // 테스트 코드: CM-082
    it('creates the owner comment as read, the others as unread, and counts unread by deal and action', async () => {
      // given: Owner(sales)의 Deal과 Action
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const act = await sales.actions.create(deal.code, action())
      const own = await sales.comments.create(deal.code, { body: 'Owner 글' })
      const admin = await make('admin')

      // when: admin이 Deal Comment와 Action Comment를 쓴다
      const dealOne = await admin.comments.create(deal.code, { body: 'admin Deal' })
      const actionOne = await admin.comments.create(deal.code, { body: 'admin Action', actionId: act.id })

      // then: Owner 글은 읽음이고 admin 글은 읽지 않음이며 집계가 맞다
      expect(own.readAt).not.toBeNull()
      expect([dealOne.readAt, actionOne.readAt]).toEqual([null, null])
      expect(await admin.comments.counts(deal.code)).toEqual({ unread: 2, byAction: { [act.id]: 1 } })
      await admin.deals.remove(deal.code, deal.code)
    })

    // 읽음 처리는 Owner만 하고(admin 403), 읽지 않은 것만 채우며 그 밖의 id는 건너뛰고, 다시 해도 같다.
    // 테스트 코드: CM-082
    it('lets only the owner mark comments read, skipping unknown and already read ids', async () => {
      // given: Owner의 Deal에 admin이 쓴 Comment 둘
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const admin = await make('admin')
      const one = await admin.comments.create(deal.code, { body: '하나' })
      await admin.comments.create(deal.code, { body: '둘' })

      // when·then: admin(Owner 아님)은 403이고 아무것도 바뀌지 않는다
      await expectRejects(admin.comments.markRead(deal.code, [one.id]), 403, 'Deal Owner만 Comment를 읽음 처리할 수 있습니다.')
      expect((await admin.comments.counts(deal.code)).unread).toBe(2)
      // when: Owner가 하나와 없는 id를 읽음 처리하고 한 번 더 한다
      const owner = await make('sales')
      await owner.comments.markRead(deal.code, [one.id, NO_SUCH_ID])
      await owner.comments.markRead(deal.code, [one.id])
      // then: 하나만 읽음이고 집계는 1건이다
      expect((await owner.comments.counts(deal.code)).unread).toBe(1)
      expect((await owner.comments.list(deal.code)).find((c) => c.id === one.id)?.readAt).not.toBeNull()
      // when·then: 빈 목록은 422, 없는 Deal은 404이다
      await expectRejects(owner.comments.markRead(deal.code, []), 422)
      await expectRejects(owner.comments.markRead('20000101-ZZZZ', [one.id]), 404)
      await (await make('admin')).deals.remove(deal.code, deal.code)
    })

    // 삭제는 작성자 sales와 admin만 하고 이력에 본문과 "삭제"가 남으며 다시 지우면 404다.
    // 테스트 코드: CM-082
    it('lets the author and admin delete, logs it, and answers 404 the second time', async () => {
      // given: sales가 쓴 Comment와 admin이 쓴 Comment
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const mine = await sales.comments.create(deal.code, { body: '내 글' })
      const admin = await make('admin')
      const theirs = await admin.comments.create(deal.code, { body: '남의 글' })

      // when·then: sales는 admin의 Comment를 못 지운다(403)
      const again = await make('sales')
      await expectRejects(again.comments.remove(theirs.id), 403, '본인 Comment 또는 admin만 삭제할 수 있습니다.')
      // when: 작성자가 지우고 admin이 남의 것을 지운다
      await again.comments.remove(mine.id)
      const boss = await make('admin')
      await boss.comments.remove(theirs.id)
      // then: 둘 다 사라지고 이력에 본문과 "삭제"가 남으며 다시 지우면 404다
      expect(await boss.comments.list(deal.code)).toEqual([])
      expect((await boss.history.list(deal.code, {}))[0]).toMatchObject({ category: 'comment', target: 'Comment', before: '남의 글', after: '삭제' })
      await expectRejects(boss.comments.remove(theirs.id), 404, 'Comment를 찾을 수 없습니다.')
      await boss.deals.remove(deal.code, deal.code)
    })

    // Action을 지우면 그 Action Comment만 함께 지워지고 Deal 삭제 영향은 Comment 건수를 준다.
    // 테스트 코드: CM-082
    it('deletes the action comments with the action and reports the comment count of a deal', async () => {
      // given: Action Comment 1건과 Deal Comment 1건
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const act = await sales.actions.create(deal.code, action())
      await sales.comments.create(deal.code, { body: 'Action 글', actionId: act.id })
      await sales.comments.create(deal.code, { body: 'Deal 글' })
      expect((await sales.deals.impact(deal.code)).commentCount).toBe(2)

      // when: Action을 지운다
      await sales.actions.remove(act.id)

      // then: Action Comment만 사라지고 이력 변경 후에 함께 지운 건수가 붙는다
      expect((await sales.comments.list(deal.code)).map((c) => c.body)).toEqual(['Deal 글'])
      expect((await sales.history.list(deal.code, {})).find((h) => h.category === 'action' && h.after.startsWith('삭제'))?.after).toBe('삭제 (Comment 1건 함께 삭제)')
      await sales.deals.remove(deal.code, deal.code)
      await expectRejects(sales.comments.list(deal.code), 404)
    })
  })
}
