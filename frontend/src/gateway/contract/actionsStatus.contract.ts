/**
 * Next Action 상태·입력 분리 계약(AC-1~5·7~12·15·18·19). mock과 실제 서버가 같은 결과를 내야 한다.
 * 호출마다 고유한 Deal을 만들고 스스로 지운다. 종료 시각은 값 자체가 아니라 "있는가"만 본다(서버 시계).
 */

import { describe, expect, it } from 'vitest'
import { action, newDeal } from './actions.contract'
import { expectRejects, type MakeGateway, NO_SUCH_ID } from './support'

const ONLY_PROGRESS = { nextAction: '', dueDate: '' } as const
const ONLY_NEXT = { progress: '' } as const

export function actionsStatusContract(make: MakeGateway): void {
  describe('actions 상태 계약', () => {
    it('registers a progress-only action with no Next Action fields and no status', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      const created = await sales.actions.create(deal.code, action(ONLY_PROGRESS))

      expect(created).toMatchObject({ progress: '고객사 방문', nextAction: null, dueDate: null, nextActionStatus: null, nextActionClosedAt: null })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('registers a Next-Action-only action as open with no progress', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      const created = await sales.actions.create(deal.code, action(ONLY_NEXT))

      expect(created).toMatchObject({ progress: null, nextAction: '견적 재전달', dueDate: '2026-12-01', nextActionStatus: 'open', nextActionClosedAt: null })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('closes as done with a memo appended after the existing memo and a closed time', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action({ memo: '기존' }))

      const closed = await sales.actions.changeNextActionStatus(created.id, { status: 'done', memo: '전달 완료' })

      expect(closed).toMatchObject({ id: created.id, nextActionStatus: 'done', memo: '기존\n전달 완료' })
      expect(Number.isNaN(Date.parse(closed.nextActionClosedAt ?? ''))).toBe(false)
      expect(await sales.actions.list(deal.code, {})).toEqual([closed])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('keeps the memo when closing without a note and uses the note alone when the memo is empty', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const withMemo = await sales.actions.create(deal.code, action({ memo: '기존' }))
      const empty = await sales.actions.create(deal.code, action({ memo: '' }))

      const a = await sales.actions.changeNextActionStatus(withMemo.id, { status: 'notDone', memo: '  ' })
      const b = await sales.actions.changeNextActionStatus(empty.id, { status: 'done', memo: ' 마무리 ' })

      expect(a).toMatchObject({ nextActionStatus: 'notDone', memo: '기존' })
      expect(b).toMatchObject({ nextActionStatus: 'done', memo: '마무리' })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('reopens a closed action: the closed time is cleared and the memo stays', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action({ memo: '기존' }))
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', memo: '끝' })

      const reopened = await sales.actions.changeNextActionStatus(created.id, { status: 'open', memo: '' })

      expect(reopened).toMatchObject({ nextActionStatus: 'open', nextActionClosedAt: null, memo: '기존\n끝' })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('moves between done and notDone', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' })

      const changed = await sales.actions.changeNextActionStatus(created.id, { status: 'notDone', memo: '취소' })

      expect(changed).toMatchObject({ nextActionStatus: 'notDone', memo: '취소' })
      expect(changed.nextActionClosedAt).not.toBeNull()
      await sales.deals.remove(deal.code, deal.code)
    })

    it('answers 409 for the same status and for an action without a Next Action, changing nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const plain = await sales.actions.create(deal.code, action({ memo: '메모' }))
      const noNext = await sales.actions.create(deal.code, action(ONLY_PROGRESS))

      await expectRejects(sales.actions.changeNextActionStatus(plain.id, { status: 'open', memo: '' }), 409, '이미 Open 상태입니다.')
      await expectRejects(
        sales.actions.changeNextActionStatus(noNext.id, { status: 'done', memo: '메모' }),
        409,
        'Next Action이 없는 Action은 상태를 바꿀 수 없습니다.',
      )

      expect((await sales.actions.list(deal.code, {})).map((a) => [a.nextActionStatus, a.memo])).toEqual([[null, ''], ['open', '메모']])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('answers 422 when reopening with a memo and 404 for an unknown action', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' })

      await expectRejects(sales.actions.changeNextActionStatus(created.id, { status: 'open', memo: '메모' }), 422)
      await expectRejects(sales.actions.changeNextActionStatus(NO_SUCH_ID, { status: 'done', memo: '' }), 404, 'Action을 찾을 수 없습니다.')

      await sales.deals.remove(deal.code, deal.code)
    })

    it('refuses the user role with 403', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const user = await make('user')

      await expectRejects(user.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' }), 403)

      const again = await make('sales')
      expect((await again.actions.list(deal.code, {}))[0]?.nextActionStatus).toBe('open')
      await again.deals.remove(deal.code, deal.code)
    })

    it('lets admin close the action of a sales', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const admin = await make('admin')

      const closed = await admin.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' })

      expect(closed.nextActionStatus).toBe('done')
      await admin.deals.remove(deal.code, deal.code)
    })

    it('writes one "Next Action" history entry per status change and none for a rejected one', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const baseline = (await sales.history.list(deal.code, {})).length

      await sales.actions.changeNextActionStatus(created.id, { status: 'done', memo: '전달 완료' })
      await expectRejects(sales.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' }), 409)

      const history = await sales.history.list(deal.code, {})
      expect(history).toHaveLength(baseline + 1)
      expect(history[0]).toMatchObject({
        category: 'action',
        target: 'Next Action',
        before: '견적 재전달 (Due 2026-12-01) · Open',
        after: '종료(수행) / Memo: 전달 완료',
      })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('removes the status when the edit clears the Next Action, and opens it when one is added', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      await sales.actions.changeNextActionStatus(created.id, { status: 'done', memo: '' })
      const base = { type: { name: '미팅' }, progress: '고객사 방문', memo: '' }

      const cleared = await sales.actions.update(created.id, { ...base, nextAction: '', dueDate: '' })
      const added = await sales.actions.update(created.id, { ...base, nextAction: '새 계획', dueDate: '2026-12-05' })

      expect(cleared).toMatchObject({ nextAction: null, dueDate: null, nextActionStatus: null, nextActionClosedAt: null })
      expect(added).toMatchObject({ nextAction: '새 계획', nextActionStatus: 'open' })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('keeps a closed status when only the content of the Next Action changes', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const closed = await sales.actions.changeNextActionStatus(created.id, { status: 'notDone', memo: '' })

      const edited = await sales.actions.update(created.id, { type: { name: '미팅' }, progress: '고객사 방문', nextAction: '바뀐 계획', dueDate: '2026-12-09', memo: '' })

      expect(edited).toMatchObject({ nextAction: '바뀐 계획', nextActionStatus: 'notDone', nextActionClosedAt: closed.nextActionClosedAt })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('filters the action list by status (closed = done or notDone) and drops rows without a Next Action', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const open = await sales.actions.create(deal.code, action({ progress: '열림' }))
      const done = await sales.actions.create(deal.code, action({ progress: '수행' }))
      const notDone = await sales.actions.create(deal.code, action({ progress: '미수행' }))
      const noNext = await sales.actions.create(deal.code, action({ progress: '진행만', ...ONLY_PROGRESS }))
      await sales.actions.changeNextActionStatus(done.id, { status: 'done', memo: '' })
      await sales.actions.changeNextActionStatus(notDone.id, { status: 'notDone', memo: '' })
      const ids = async (nextActionStatus?: 'open' | 'done' | 'notDone' | 'closed') =>
        (await sales.actions.list(deal.code, { sort: 'actedAt', order: 'asc', ...(nextActionStatus ? { nextActionStatus } : {}) })).map((a) => a.id)

      expect(await ids('open')).toEqual([open.id])
      expect(await ids('done')).toEqual([done.id])
      expect(await ids('notDone')).toEqual([notDone.id])
      expect(await ids('closed')).toEqual([done.id, notDone.id])
      expect(await ids()).toEqual([open.id, done.id, notDone.id, noNext.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('sorts by due date with the rows without a Due Date last', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const noDue = await sales.actions.create(deal.code, action(ONLY_PROGRESS))
      const late = await sales.actions.create(deal.code, action({ dueDate: '2026-12-30' }))
      const early = await sales.actions.create(deal.code, action({ dueDate: '2026-12-02' }))

      const byDue = (await sales.actions.list(deal.code, { sort: 'dueDate', order: 'asc' })).map((a) => a.id)
      const byDueDesc = (await sales.actions.list(deal.code, { sort: 'dueDate', order: 'desc' })).map((a) => a.id)

      expect(byDue).toEqual([early.id, late.id, noDue.id])
      expect(byDueDesc).toEqual([late.id, early.id, noDue.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('sorts by status open, done, notDone in either direction with the rows without a Next Action last', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const notDone = await sales.actions.create(deal.code, action({ progress: '미수행' }))
      const noNext = await sales.actions.create(deal.code, action({ progress: '진행만', ...ONLY_PROGRESS }))
      const done = await sales.actions.create(deal.code, action({ progress: '수행' }))
      const open = await sales.actions.create(deal.code, action({ progress: '열림' }))
      await sales.actions.changeNextActionStatus(done.id, { status: 'done', memo: '' })
      await sales.actions.changeNextActionStatus(notDone.id, { status: 'notDone', memo: '' })
      const ids = async (order: 'asc' | 'desc') =>
        (await sales.actions.list(deal.code, { sort: 'nextActionStatus', order })).map((a) => a.id)

      expect(await ids('asc')).toEqual([open.id, done.id, notDone.id, noNext.id])
      expect(await ids('desc')).toEqual([notDone.id, done.id, open.id, noNext.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('shows the latest action that has a Next Action in the deal summary, skipping progress-only rows', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await sales.actions.create(deal.code, action({ nextAction: '기준 계획', dueDate: '2026-12-07' }))
      await sales.actions.create(deal.code, action({ progress: '전화만', ...ONLY_PROGRESS }))

      const read = await sales.deals.get(deal.code)

      expect(read.nextAction).toEqual({ text: '기준 계획', dueDate: '2026-12-07', status: 'open' })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('has no Next Action in the summary when no action ever had one', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await sales.actions.create(deal.code, action(ONLY_PROGRESS))

      expect((await sales.deals.get(deal.code)).nextAction).toBeNull()
      await sales.deals.remove(deal.code, deal.code)
    })

    it('refreshes the last update with a progress-only action', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      const created = await sales.actions.create(deal.code, action(ONLY_PROGRESS))

      expect((await sales.deals.get(deal.code)).lastUpdatedAt).toBe(created.actedAt)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('filters the deal list by the status of the basis row (closed included) and by none when the deal has no Next Action', async () => {
      const sales = await make('sales')
      const a = await newDeal(sales)
      const b = await newDeal(sales)
      const c = await newDeal(sales)
      const basis = await sales.actions.create(a.code, action())
      await sales.actions.changeNextActionStatus(basis.id, { status: 'done', memo: '' })
      await sales.actions.create(a.code, action(ONLY_PROGRESS)) // 기준 행 뒤의 진행사항만 Action
      await sales.actions.create(b.code, action())
      await sales.actions.create(c.code, action(ONLY_PROGRESS))
      const codes = async (nextActionStatus: 'open' | 'done' | 'notDone' | 'closed') =>
        (await sales.deals.list({ nextActionStatus, limit: 100 })).items.map((d) => d.code).filter((code) => [a.code, b.code, c.code].includes(code))

      expect(await codes('open')).toEqual([b.code])
      expect(await codes('done')).toEqual([a.code])
      expect(await codes('closed')).toEqual([a.code])
      expect(await codes('notDone')).toEqual([])
      for (const deal of [a, b, c]) await sales.deals.remove(deal.code, deal.code)
    })
  })
}
