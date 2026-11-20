/**
 * Next Action 상태·입력 분리 계약. mock과 실제 서버가 같은 결과를 내야 한다.
 * 호출마다 고유한 Deal을 만들고 스스로 지운다. 종료 시각은 값 자체가 아니라 "있는가"만 본다(서버 시계).
 */

import { describe, expect, it } from 'vitest'
import { action, newDeal } from './actions.contract'
import { expectRejects, type MakeGateway, NO_SUCH_ID } from './support'

const ONLY_PROGRESS = { nextAction: '', dueDate: '' } as const
const ONLY_NEXT = { progress: '' } as const

export function actionsStatusContract(make: MakeGateway): void {
  describe('actions 상태 계약', () => {
    // 진행사항만 있는 Action은 Next Action·Due Date·상태·종료 시각이 모두 null이다.
    // 테스트 코드: AC-006
    it('진행사항만 등록하면 Next Action·Due Date·상태가 모두 비어 있다', async () => {
      // given: 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when: 진행사항만 있는 Action을 등록한다
      const created = await sales.actions.create(deal.code, action(ONLY_PROGRESS))

      // then: Next Action 관련 필드가 모두 null이다
      expect(created).toMatchObject({ progress: '고객사 방문', nextAction: null, dueDate: null, nextActionStatus: null, nextActionClosedOn: null })
      await sales.deals.remove(deal.code, deal.code)
    })

    // Next Action만 있는 Action은 진행사항이 null이고 상태가 Open이다.
    // 테스트 코드: AC-007
    it('Next Action만 등록하면 진행사항이 비어 있고 상태가 Open이다', async () => {
      // given: 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when: Next Action과 Due Date만 있는 Action을 등록한다
      const created = await sales.actions.create(deal.code, action(ONLY_NEXT))

      // then: 진행사항은 null이고 상태는 open이다
      expect(created).toMatchObject({ progress: null, nextAction: '견적 재전달', dueDate: '2026-12-01', nextActionStatus: 'open', nextActionClosedOn: null })
      await sales.deals.remove(deal.code, deal.code)
    })

    // Comment를 붙여 종료(수행)하면 그 Action의 새 Comment가 생기고 종료 시각이 생긴다(mock과 실제 서버 공통).
    // 테스트 코드: NA-068, CM-082
    it('closes as done with a comment as a new action comment and a closed time', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Open Action이 있다.
      const created = await sales.actions.create(deal.code, action())

      // when: Comment "전달 완료"로 종료(수행)한다.
      const closed = await sales.actions.changeNextActionStatus(created.id, { status: 'done', comment: '전달 완료' })

      // then: 종료 시각이 있고 목록의 행과 같으며 Action Comment 1건이 생긴다.
      expect(closed).toMatchObject({ id: created.id, nextActionStatus: 'done' })
      expect(closed.nextActionClosedOn).toMatch(/^\d{4}-\d{2}-\d{2}$/) // 종료일은 시각 없는 날짜다
      expect(await sales.actions.list(deal.code, {})).toEqual([closed])
      expect((await sales.comments.list(deal.code, { actionId: created.id })).map((c) => c.body)).toEqual(['전달 완료'])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 공백 Comment는 Comment를 만들지 않고, 앞뒤 공백이 있는 Comment는 trim해 남긴다.
    // 테스트 코드: NA-068, CM-082
    it('creates no comment for a blank note and a trimmed comment otherwise', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Open Action 둘이 있다.
      const first = await sales.actions.create(deal.code, action())
      const second = await sales.actions.create(deal.code, action())

      // when: 각각 공백 Comment와 앞뒤 공백이 있는 Comment로 종료한다.
      await sales.actions.changeNextActionStatus(first.id, { status: 'notDone', comment: '  ' })
      await sales.actions.changeNextActionStatus(second.id, { status: 'done', comment: ' 마무리 ' })

      // then: 앞은 Comment가 없고 뒤는 trim한 Comment 1건이다.
      expect(await sales.comments.list(deal.code, { actionId: first.id })).toEqual([])
      expect((await sales.comments.list(deal.code, { actionId: second.id })).map((c) => c.body)).toEqual(['마무리'])
      await sales.deals.remove(deal.code, deal.code)
    })

    // Open으로 되돌리면 종료 시각이 없어지고 만든 Comment는 남는다.
    // 테스트 코드: NA-068, CM-082
    it('reopens a closed action: the closed time is cleared and the comment stays', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Comment "끝"을 붙여 종료(수행)한 Action이 있다.
      const created = await sales.actions.create(deal.code, action())
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', comment: '끝' })

      // when: open으로 바꾼다.
      const reopened = await sales.actions.changeNextActionStatus(created.id, { status: 'open', comment: '' })

      // then: 상태 open, 종료 시각 null이고 Comment "끝"이 남아 있다.
      expect(reopened).toMatchObject({ nextActionStatus: 'open', nextActionClosedOn: null })
      expect((await sales.comments.list(deal.code, { actionId: created.id })).map((c) => c.body)).toEqual(['끝'])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 종료(수행)에서 종료(미수행)으로 바로 바꾼다.
    // 테스트 코드: NA-068
    it('moves between done and notDone', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: 종료(수행)된 Action이 있다.
      const created = await sales.actions.create(deal.code, action())
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' })

      // when: notDone, Comment "취소"로 바꾼다.
      const changed = await sales.actions.changeNextActionStatus(created.id, { status: 'notDone', comment: '취소' })

      // then: 종료(미수행)이 되고 종료 시각이 있다.
      expect(changed).toMatchObject({ nextActionStatus: 'notDone' })
      expect(changed.nextActionClosedOn).not.toBeNull()
      await sales.deals.remove(deal.code, deal.code)
    })

    // 같은 상태와 Next Action 없는 Action은 409이고 아무것도 바꾸지 않는다.
    // 테스트 코드: NA-068
    it('answers 409 for the same status and for an action without a Next Action, changing nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Open Action과 진행사항만 Action이 있다.
      const plain = await sales.actions.create(deal.code, action())
      const noNext = await sales.actions.create(deal.code, action(ONLY_PROGRESS))

      // when·then: 같은 상태 open은 409 "이미 Open 상태입니다."다.
      await expectRejects(sales.actions.changeNextActionStatus(plain.id, { status: 'open', comment: '' }), 409, '이미 Open 상태입니다.')
      await expectRejects(
        // when·then: 진행사항만 Action은 409 Next Action 없음 문구다.
        sales.actions.changeNextActionStatus(noNext.id, { status: 'done', comment: '메모' }),
        409,
        'Next Action이 없는 Action은 상태를 바꿀 수 없습니다.',
      )

      // then: 상태가 그대로이고 Comment가 생기지 않았다.
      expect((await sales.actions.list(deal.code, {})).map((a) => a.nextActionStatus)).toEqual([null, 'open'])
      expect(await sales.comments.list(deal.code)).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    // Open으로 되돌리며 Comment를 보내면 422이고 없는 Action은 404다.
    // 테스트 코드: NA-068
    it('answers 422 when reopening with a comment and 404 for an unknown action', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: 종료(수행)된 Action이 있다.
      const created = await sales.actions.create(deal.code, action())
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' })

      // when·then: open+Comment는 422다.
      await expectRejects(sales.actions.changeNextActionStatus(created.id, { status: 'open', comment: '메모' }), 422)
      // when·then: 없는 Action은 404 "Action을 찾을 수 없습니다."다.
      await expectRejects(sales.actions.changeNextActionStatus(NO_SUCH_ID, { status: 'done', comment: '' }), 404, 'Action을 찾을 수 없습니다.')

      await sales.deals.remove(deal.code, deal.code)
    })

    // user 역할은 403이고 Action이 그대로다.
    // 테스트 코드: NA-068
    it('refuses the user role with 403', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: sales가 만든 Open Action이 있다.
      const created = await sales.actions.create(deal.code, action())
      const user = await make('user')

      // when·then: user가 상태를 바꾸면 403이다.
      await expectRejects(user.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' }), 403)

      const again = await make('sales')
      // then: Action은 Open 그대로다.
      expect((await again.actions.list(deal.code, {}))[0]?.nextActionStatus).toBe('open')
      await again.deals.remove(deal.code, deal.code)
    })

    // admin은 sales의 Action을 종료할 수 있다.
    // 테스트 코드: NA-068
    it('lets admin close the action of a sales', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: sales가 만든 Open Action이 있다.
      const created = await sales.actions.create(deal.code, action())
      const admin = await make('admin')

      // when: admin이 종료(수행)한다.
      const closed = await admin.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' })

      // then: 종료(수행)이 된다.
      expect(closed.nextActionStatus).toBe('done')
      await admin.deals.remove(deal.code, deal.code)
    })

    // 상태 변경마다 History 1건이 남고 거절된 변경은 남기지 않는다.
    // 테스트 코드: NA-068
    it('writes one "Next Action" history entry per status change and none for a rejected one', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Open Action이 있다.
      const created = await sales.actions.create(deal.code, action())
      const baseline = (await sales.history.list(deal.code, {})).length

      // when: 종료(수행)+Comment로 바꾸고, 같은 상태로 다시 바꾸려다 거절된다.
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', comment: '전달 완료' })
      await expectRejects(sales.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' }), 409)

      // then: History가 Next Action 줄과 Comment 등록 줄 2건 늘고 변경 전/후 문구가 정해진 형식이다(거절된 변경은 없다).
      const history = await sales.history.list(deal.code, {})
      expect(history).toHaveLength(baseline + 2)
      expect(history[1]).toMatchObject({
        category: 'action',
        target: 'Next Action',
        before: '견적 재전달 (Due 2026-12-01) · Open',
        after: '종료(수행)',
      })
      expect(history[0]).toMatchObject({ category: 'comment', before: '', after: '등록: 전달 완료' })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 수정으로 Next Action을 비우면 상태가 사라지고 다시 채우면 Open이 된다.
    // 테스트 코드: AC-050, AC-051
    it('수정으로 Next Action을 비우면 상태가 없어지고 다시 채우면 Open이 된다', async () => {
      // given: 종료(수행)한 Next Action이 있는 Action
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', comment: '' })
      const base = { type: { name: '미팅' }, progress: '고객사 방문', comment: '' }

      // when: Next Action을 비워 수정한 뒤 새 Next Action을 채워 다시 수정한다
      const cleared = await sales.actions.update(created.id, { ...base, nextAction: '', dueDate: '' })
      const added = await sales.actions.update(created.id, { ...base, nextAction: '새 계획', dueDate: '2026-12-05' })

      // then: 비운 결과는 상태·종료 시각이 null이고 채운 결과는 Open이다
      expect(cleared).toMatchObject({ nextAction: null, dueDate: null, nextActionStatus: null, nextActionClosedOn: null })
      expect(added).toMatchObject({ nextAction: '새 계획', nextActionStatus: 'open' })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 종료된 Next Action의 내용을 고쳐도 종료 상태와 종료 시각은 그대로다.
    // 테스트 코드: AC-052
    it('종료된 Next Action의 내용만 고치면 종료 상태와 종료 시각이 유지된다', async () => {
      // given: 종료(미수행)한 Next Action이 있는 Action
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const closed = await sales.actions.changeNextActionStatus(created.id, { status: 'notDone', comment: '' })

      // when: Next Action 내용과 Due Date만 고쳐 수정한다
      const edited = await sales.actions.update(created.id, { type: { name: '미팅' }, progress: '고객사 방문', nextAction: '바뀐 계획', dueDate: '2026-12-09' })

      // then: 내용은 바뀌고 상태·종료 시각은 그대로다
      expect(edited).toMatchObject({ nextAction: '바뀐 계획', nextActionStatus: 'notDone', nextActionClosedOn: closed.nextActionClosedOn })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 상태 필터는 그 상태만 고르고 closed는 종료 둘 다이며 Next Action 없는 행은 뺀다.
    // 테스트 코드: NA-068
    it('filters the action list by status (closed = done or notDone) and drops rows without a Next Action', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: 열림·수행·미수행·진행만 Action이 있다.
      const open = await sales.actions.create(deal.code, action({ progress: '열림' }))
      const done = await sales.actions.create(deal.code, action({ progress: '수행' }))
      const notDone = await sales.actions.create(deal.code, action({ progress: '미수행' }))
      const noNext = await sales.actions.create(deal.code, action({ progress: '진행만', ...ONLY_PROGRESS }))
      await sales.actions.changeNextActionStatus(done.id, { status: 'done', comment: '' })
      await sales.actions.changeNextActionStatus(notDone.id, { status: 'notDone', comment: '' })
      // when: 필터를 open, done, notDone, closed, 없음으로 조회한다.
      const ids = async (nextActionStatus?: 'open' | 'done' | 'notDone' | 'closed') =>
        (await sales.actions.list(deal.code, { sort: 'actedAt', order: 'asc', ...(nextActionStatus ? { nextActionStatus } : {}) })).map((a) => a.id)

      // then: 각 필터에 맞는 행만 나오고 필터가 없으면 넷 다 나온다.
      expect(await ids('open')).toEqual([open.id])
      expect(await ids('done')).toEqual([done.id])
      expect(await ids('notDone')).toEqual([notDone.id])
      expect(await ids('closed')).toEqual([done.id, notDone.id])
      expect(await ids()).toEqual([open.id, done.id, notDone.id, noNext.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    // Due Date 정렬은 Due가 없는 행을 방향과 관계없이 맨 뒤에 둔다.
    // 테스트 코드: NA-068
    it('sorts by due date with the rows without a Due Date last', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Due가 없는 행과 늦은·빠른 Due 행이 있다.
      const noDue = await sales.actions.create(deal.code, action(ONLY_PROGRESS))
      const late = await sales.actions.create(deal.code, action({ dueDate: '2026-12-30' }))
      const early = await sales.actions.create(deal.code, action({ dueDate: '2026-12-02' }))

      // when: due_date 오름차순·내림차순으로 조회한다.
      const byDue = (await sales.actions.list(deal.code, { sort: 'dueDate', order: 'asc' })).map((a) => a.id)
      const byDueDesc = (await sales.actions.list(deal.code, { sort: 'dueDate', order: 'desc' })).map((a) => a.id)

      // then: Due 없음이 두 방향 모두 맨 뒤다.
      expect(byDue).toEqual([early.id, late.id, noDue.id])
      expect(byDueDesc).toEqual([late.id, early.id, noDue.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 상태 정렬은 열림·수행·미수행 순이고 상태 없음은 방향과 관계없이 맨 뒤다.
    // 테스트 코드: NA-068
    it('sorts by status open, done, notDone in either direction with the rows without a Next Action last', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: 미수행·진행만·수행·열림 행이 있다.
      const notDone = await sales.actions.create(deal.code, action({ progress: '미수행' }))
      const noNext = await sales.actions.create(deal.code, action({ progress: '진행만', ...ONLY_PROGRESS }))
      const done = await sales.actions.create(deal.code, action({ progress: '수행' }))
      const open = await sales.actions.create(deal.code, action({ progress: '열림' }))
      await sales.actions.changeNextActionStatus(done.id, { status: 'done', comment: '' })
      await sales.actions.changeNextActionStatus(notDone.id, { status: 'notDone', comment: '' })
      // when: 상태 정렬을 오름차순·내림차순으로 조회한다.
      const ids = async (order: 'asc' | 'desc') =>
        (await sales.actions.list(deal.code, { sort: 'nextActionStatus', order })).map((a) => a.id)

      // then: 열림, 수행, 미수행, 진행만 순과 그 반대(진행만은 맨 뒤)다.
      expect(await ids('asc')).toEqual([open.id, done.id, notDone.id, noNext.id])
      expect(await ids('desc')).toEqual([notDone.id, done.id, open.id, noNext.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    // Deal의 Next Action은 Next Action이 있는 가장 최근 Action이고 더 최근의 진행사항만 Action은 대신하지 않는다.
    // 테스트 코드: RK-001
    it('Deal 요약의 Next Action은 진행사항만 Action을 건너뛰고 Next Action이 있는 가장 최근 Action이다', async () => {
      // given: Next Action이 있는 Action 뒤에 진행사항만 Action이 등록된 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const planned = await sales.actions.create(deal.code, action({ nextAction: '기준 계획', dueDate: '2026-12-07' }))
      await sales.actions.create(deal.code, action({ progress: '전화만', ...ONLY_PROGRESS }))

      // when: Deal을 읽는다
      const read = await sales.deals.get(deal.code)

      // then: Next Action 요약이 앞선 Action의 것이다
      expect(read.nextAction).toEqual({ text: '기준 계획', dueDate: '2026-12-07', status: 'open', actionId: planned.id })
      await sales.deals.remove(deal.code, deal.code)
    })

    // Next Action이 있던 Action이 없으면 Deal 요약에 Next Action이 없다.
    it('Next Action이 있던 Action이 없으면 Deal 요약의 Next Action이 비어 있다', async () => {
      // given: 진행사항만 Action이 있는 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await sales.actions.create(deal.code, action(ONLY_PROGRESS))

      // when·then: Deal을 읽으면 Next Action이 null이다
      expect((await sales.deals.get(deal.code)).nextAction).toBeNull()
      await sales.deals.remove(deal.code, deal.code)
    })

    // 진행사항만 Action도 최종 업데이트를 그 수행 시각으로 새로 한다.
    // 테스트 코드: RK-004
    it('진행사항만 등록해도 Deal의 최종 업데이트가 그 수행 시각이 된다', async () => {
      // given: 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when: 진행사항만 있는 Action을 등록한다
      const created = await sales.actions.create(deal.code, action(ONLY_PROGRESS))

      // then: Deal의 최종 업데이트일이 Action의 수행일이다
      expect((await sales.deals.get(deal.code)).lastUpdatedOn).toBe(created.actedOn)
      await sales.deals.remove(deal.code, deal.code)
    })

    // Deal 목록의 Next Action 상태 필터는 기준 행의 상태로 거르고 Next Action이 없는 Deal은 빠진다.
    // 테스트 코드: DL-033
    it('Deal 목록의 Next Action 상태 필터는 기준 행 상태로 거르고 Next Action이 없는 Deal은 뺀다', async () => {
      // given: 종료한 기준 행(뒤에 진행사항만 Action)·Open 기준 행·Next Action 없는 Deal
      const sales = await make('sales')
      const a = await newDeal(sales)
      const b = await newDeal(sales)
      const c = await newDeal(sales)
      const basis = await sales.actions.create(a.code, action())
      await sales.actions.changeNextActionStatus(basis.id, { status: 'done', comment: '' })
      await sales.actions.create(a.code, action(ONLY_PROGRESS)) // 기준 행 뒤의 진행사항만 Action
      await sales.actions.create(b.code, action())
      await sales.actions.create(c.code, action(ONLY_PROGRESS))
      const codes = async (nextActionStatus: 'open' | 'done' | 'notDone' | 'closed') =>
        (await sales.deals.list({ nextActionStatus, limit: 100 })).items.map((d) => d.code).filter((code) => [a.code, b.code, c.code].includes(code))

      // when·then: open은 Open 기준 행의 Deal, done·closed는 종료한 기준 행의 Deal만 나오고 notDone은 비어 있다
      expect(await codes('open')).toEqual([b.code])
      expect(await codes('done')).toEqual([a.code])
      expect(await codes('closed')).toEqual([a.code])
      expect(await codes('notDone')).toEqual([])
      for (const deal of [a, b, c]) await sales.deals.remove(deal.code, deal.code)
    })
  })
}
