/**
 * Action 계약(AC-01~16, Q5·Q6, R-11~R-14). mock과 실제 서버가 같은 결과를 내야 한다.
 * 호출마다 고유한 Deal을 만들고 스스로 지운다(Deal 삭제가 Action을 함께 지운다). 시드에 기대지 않는다.
 * 다른 사용자 세션이 필요한 Q8 403 사례는 mock 단위 테스트와 백엔드 functional이 맡는다(여기서는 admin의 타인 Action 수정·삭제만).
 */

import { describe, expect, it } from 'vitest'
import type { ActionInput, DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const REVENUE_NEEDED = 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'
const ACTED_REVERSED = '수행일 범위의 시작은 끝보다 늦을 수 없습니다.'
const DUE_REVERSED = 'Due Date 범위의 시작은 끝보다 늦을 수 없습니다.'

export async function newDeal(gateway: Gateway) {
  const me = await gateway.auth.me()
  const input: DealInput = {
    name: unique('deal'),
    ownerId: me.id,
    vendorId: null,
    solution: 'ITDR',
    users: 10,
    statusKey: 'prospecting',
    forecastKey: 'pipeline',
    revenueAmount: 1_000_000,
    revenueDate: '2027-02-15',
    customer: { contactId: null, company: unique('co'), name: unique('nm'), title: '', email: null, phone: null },
    partner: null,
    quote: { submitted: null, submittedDate: null },
    poc: { state: null, completedDate: null },
    procurement: '',
    bant: { budget: null, authority: null, need: null, timeline: null },
  }
  return gateway.deals.create(input)
}

export const action = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-12-01',
  memo: '',
  ...over,
})

/** 실행 환경의 로컬 달력 날짜(업무 날짜, Q2). */
function localDay(iso: string, plusDays = 0): string {
  const d = new Date(iso)
  d.setDate(d.getDate() + plusDays)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function actionsContract(make: MakeGateway): void {
  describe('actions 계약', () => {
    it('registers an action as the requester with the current status, forecast and a server time', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await newDeal(sales)

      const created = await sales.actions.create(deal.code, action({ memo: '메모' }))

      expect(created).toMatchObject({
        dealCode: deal.code,
        type: '미팅',
        progress: '고객사 방문',
        nextAction: '견적 재전달',
        dueDate: '2026-12-01',
        memo: '메모',
        statusKey: 'prospecting',
        forecastKey: 'pipeline',
        actor: { id: me.id },
      })
      expect(Number.isNaN(Date.parse(created.actedAt))).toBe(false)
      expect(await sales.actions.list(deal.code, {})).toEqual([created])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('refuses the user role to register with 403', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const user = await make('user')

      await expectRejects(user.actions.create(deal.code, action()), 403)

      const again = await make('sales')
      expect(await again.actions.list(deal.code, {})).toEqual([])
      await again.deals.remove(deal.code, deal.code)
    })

    it('checks the deal first, then "progress or Next Action", then the Due Date rules, storing nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      await expectRejects(sales.actions.create('20000101-ZZZZ', action({ progress: ' ' })), 404)
      await expectRejects(sales.actions.create(deal.code, action({ progress: ' ', nextAction: ' ', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')
      await expectRejects(sales.actions.create(deal.code, action({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
      await expectRejects(sales.actions.create(deal.code, action({ nextAction: ' ' })), 422, 'Next Action 없이 Due Date를 입력할 수 없습니다.')

      expect(await sales.actions.list(deal.code, {})).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('accepts a past due date and trims the three texts', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      const created = await sales.actions.create(deal.code, action({ dueDate: '2000-01-01', progress: '  진행  ', nextAction: ' 다음 ', memo: '  메모  ' }))

      expect(created).toMatchObject({ dueDate: '2000-01-01', progress: '진행', nextAction: '다음', memo: '메모' })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('saves 5,000 / 5,000 / 20,000 character texts in full (no length limit)', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const progress = '가'.repeat(5000)
      const nextAction = '나'.repeat(5000)
      const memo = '다'.repeat(20000)

      const created = await sales.actions.create(deal.code, action({ progress, nextAction, memo }))

      expect(created).toMatchObject({ progress, nextAction, memo })
      expect((await sales.actions.list(deal.code, {}))[0]).toMatchObject({ progress, nextAction, memo })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('puts the latest action in the deal summary and writes one history entry with the Memo part', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const baseline = (await sales.history.list(deal.code, {})).length

      await sales.actions.create(deal.code, action({ memo: '메모' }))

      const read = await sales.deals.get(deal.code)
      expect(read.nextAction).toEqual({ text: '견적 재전달', dueDate: '2026-12-01', status: 'open' })
      const history = await sales.history.list(deal.code, {})
      expect(history).toHaveLength(baseline + 1)
      expect(history[0]).toMatchObject({
        category: 'action',
        target: 'Action',
        before: '',
        after: '등록: 미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-12-01) / Memo: 메모',
      })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('leaves out the Memo part of the history summary when the memo is empty', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      await sales.actions.create(deal.code, action())

      expect((await sales.history.list(deal.code, {}))[0]?.after).toBe('등록: 미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-12-01)')
      await sales.deals.remove(deal.code, deal.code)
    })

    it('clips a long history summary to 1,000 characters ending with an ellipsis, keeping the action whole', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const progress = '가'.repeat(2000)

      const created = await sales.actions.create(deal.code, action({ progress }))

      const after = (await sales.history.list(deal.code, {}))[0]?.after ?? ''
      expect(Array.from(after)).toHaveLength(1000)
      expect(after.endsWith('…')).toBe(true)
      expect(created.progress).toBe(progress)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('refuses to close with an action when the actual revenue is missing and stores nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      await expectRejects(
        sales.actions.create(deal.code, action({ statusChanges: [{ change: { field: 'statusKey', value: 'contract_completed' } }] })),
        422,
        REVENUE_NEEDED,
      )

      expect(await sales.actions.list(deal.code, {})).toEqual([])
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('changes the deal together with the action and stores the post-change status and forecast', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      const created = await sales.actions.create(
        deal.code,
        action({
          statusChanges: [{
            change: { field: 'statusKey', value: 'contract_completed' },
            resolution: { revenueAmount: 5_000_000, revenueDate: '2026-10-15' },
          }],
        }),
      )

      expect(created).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 5_000_000 })
      const history = await sales.history.list(deal.code, {})
      expect(history[0]?.category).toBe('action')
      expect(history.slice(0, 8).map((h) => h.category)).toEqual(expect.arrayContaining(['status', 'forecast']))
      await sales.deals.remove(deal.code, deal.code)
    })

    it('registers only the action when the requested status equals the current one', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const baseline = (await sales.history.list(deal.code, {})).length

      const created = await sales.actions.create(deal.code, action({ statusChanges: [{ change: { field: 'statusKey', value: 'prospecting' } }] }))

      expect(created).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      expect(await sales.history.list(deal.code, {})).toHaveLength(baseline + 1)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('keeps the status and forecast of an action when the deal changes later or the action is edited', async () => {
      const admin = await make('admin')
      const other = (await admin.codes.list('forecast')).find((c) => c.outcome === 'open' && c.key !== 'pipeline')
      if (!other) throw new Error('다른 Forecast 코드가 필요합니다.')
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())

      await sales.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: other.key } })
      const edited = await sales.actions.update(created.id, action({ progress: '수정' }))

      expect(edited).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline', actedAt: created.actedAt, actor: created.actor })
      expect((await sales.actions.list(deal.code, {}))[0]).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('writes before and "수정: " after on a real change and nothing on an unchanged edit', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const afterCreate = await sales.history.list(deal.code, {})

      await sales.actions.update(created.id, action({ progress: `  ${created.progress}  ` }))
      expect(await sales.history.list(deal.code, {})).toEqual(afterCreate)

      await sales.actions.update(created.id, action({ type: { name: '통화' }, progress: '전화', memo: '메모' }))
      const history = await sales.history.list(deal.code, {})
      expect(history).toHaveLength(afterCreate.length + 1)
      expect(history[0]).toMatchObject({
        category: 'action',
        before: '미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-12-01)',
        after: '수정: 통화 · 전화 / Next Action: 견적 재전달 (Due 2026-12-01) / Memo: 메모',
      })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('validates an edit in the same order and answers 404 for an unknown action', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())

      await expectRejects(sales.actions.update(created.id, action({ progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')
      await expectRejects(sales.actions.update(created.id, action({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
      await expectRejects(sales.actions.update(created.id, action({ nextAction: '', dueDate: '2026-12-01' })), 422, 'Next Action 없이 Due Date를 입력할 수 없습니다.')
      await expectRejects(sales.actions.update(NO_SUCH_ID, action()), 404, 'Action을 찾을 수 없습니다.')

      await sales.deals.remove(deal.code, deal.code)
    })

    it('lets admin edit and delete the action of a sales, logging admin as the changer', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const admin = await make('admin')
      const adminId = (await admin.auth.me()).id

      const edited = await admin.actions.update(created.id, action({ progress: '관리자 수정' }))
      expect(edited).toMatchObject({ progress: '관리자 수정', actor: created.actor })
      expect((await admin.history.list(deal.code, {}))[0]).toMatchObject({ category: 'action', by: { id: adminId } })

      await admin.actions.remove(created.id)
      expect(await admin.actions.list(deal.code, {})).toEqual([])
      expect((await admin.history.list(deal.code, {}))[0]).toMatchObject({ after: '삭제', by: { id: adminId } })
      await admin.deals.remove(deal.code, deal.code)
    })

    it('moves the deal next action back to the previous action when the latest one is deleted', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await sales.actions.create(deal.code, action({ nextAction: '첫 Next', dueDate: '2026-12-01' }))
      const latest = await sales.actions.create(deal.code, action({ nextAction: '둘째 Next', dueDate: '2026-12-09' }))
      expect((await sales.deals.get(deal.code)).nextAction).toEqual({ text: '둘째 Next', dueDate: '2026-12-09', status: 'open' })

      await sales.actions.remove(latest.id)

      expect((await sales.deals.get(deal.code)).nextAction).toEqual({ text: '첫 Next', dueDate: '2026-12-01', status: 'open' })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('answers 404 when deleting an unknown action', async () => {
      const sales = await make('sales')

      await expectRejects(sales.actions.remove(NO_SUCH_ID), 404, 'Action을 찾을 수 없습니다.')
    })

    it('filters the acted date by whole local days with both ends included', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const day = localDay(created.actedAt)
      const ids = async (from: string, to: string) => (await sales.actions.list(deal.code, { actedFrom: from, actedTo: to })).map((a) => a.id)

      expect(await ids(day, day)).toEqual([created.id])
      expect(await ids(localDay(created.actedAt, -3), day)).toEqual([created.id])
      expect(await ids(day, localDay(created.actedAt, 3))).toEqual([created.id])
      expect(await ids(localDay(created.actedAt, 1), localDay(created.actedAt, 2))).toEqual([])
      expect(await ids(localDay(created.actedAt, -2), localDay(created.actedAt, -1))).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('filters the due date with both ends included', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action({ dueDate: '2026-12-24' }))
      const ids = async (from?: string, to?: string) => (await sales.actions.list(deal.code, { dueFrom: from, dueTo: to })).map((a) => a.id)

      expect(await ids('2026-12-24', '2026-12-24')).toEqual([created.id])
      expect(await ids('2026-12-25', undefined)).toEqual([])
      expect(await ids(undefined, '2026-12-23')).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('rejects a reversed acted range and a reversed due range with their own messages', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      await expectRejects(sales.actions.list(deal.code, { actedFrom: '2026-10-20', actedTo: '2026-10-01' }), 422, ACTED_REVERSED)
      await expectRejects(sales.actions.list(deal.code, { dueFrom: '2026-10-20', dueTo: '2026-10-01' }), 422, DUE_REVERSED)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('combines type, keyword (progress, Next Action, Memo, case-insensitive) and actor with AND', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await newDeal(sales)
      const call = await sales.actions.create(deal.code, action({ type: { name: '통화' }, progress: 'Alpha 통화' }))
      await sales.actions.create(deal.code, action({ type: { name: '미팅' }, progress: 'Alpha 미팅' }))
      const viaMemo = await sales.actions.create(deal.code, action({ type: { name: '이메일' }, memo: `긴 메모 ${'x'.repeat(3000)} NEEDLE 끝` }))
      const ids = async (q: Parameters<Gateway['actions']['list']>[1]) => (await sales.actions.list(deal.code, q)).map((a) => a.id)
      const types = await sales.actionTypes.list()
      const typeId = (name: string) => types.find((t) => t.name === name)?.id ?? NO_SUCH_ID

      expect(await ids({ typeId: typeId('통화'), keyword: 'alpha' })).toEqual([call.id])
      expect(await ids({ keyword: 'needle' })).toEqual([viaMemo.id])
      expect(await ids({ actorId: me.id, typeId: typeId('이메일') })).toEqual([viaMemo.id])
      expect(await ids({ actorId: NO_SUCH_ID })).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('sorts by due date soonest first and by default newest first', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const late = await sales.actions.create(deal.code, action({ dueDate: '2026-12-30' }))
      const early = await sales.actions.create(deal.code, action({ dueDate: '2026-12-02' }))
      const middle = await sales.actions.create(deal.code, action({ dueDate: '2026-12-15' }))

      const byDue = (await sales.actions.list(deal.code, { sort: 'dueDate', order: 'asc' })).map((a) => a.id)
      const byDueDesc = (await sales.actions.list(deal.code, { sort: 'dueDate', order: 'desc' })).map((a) => a.id)
      const byDefault = (await sales.actions.list(deal.code, {})).map((a) => a.id)

      expect(byDue).toEqual([early.id, middle.id, late.id])
      expect(byDueDesc).toEqual([late.id, middle.id, early.id])
      expect(byDefault).toEqual([middle.id, early.id, late.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('sorts by type name case-insensitively in either direction, with the same ties kept newest first', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const beta = await sales.actions.create(deal.code, action({ type: { name: 'Beta' } }))
      const call = await sales.actions.create(deal.code, action({ type: { name: '통화' } }))
      const alpha = await sales.actions.create(deal.code, action({ type: { name: 'alpha' } }))
      const meeting = await sales.actions.create(deal.code, action({ type: { name: '미팅' } }))
      const ids = async (order: 'asc' | 'desc') => (await sales.actions.list(deal.code, { sort: 'type', order })).map((a) => a.id)

      expect(await ids('asc')).toEqual([alpha.id, beta.id, meeting.id, call.id])
      expect(await ids('desc')).toEqual([call.id, meeting.id, beta.id, alpha.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('sorts by actor name and keeps the newest first among the same actor in both directions', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const older = await sales.actions.create(deal.code, action({ progress: '먼저' }))
      const newer = await sales.actions.create(deal.code, action({ progress: '나중' }))

      const asc = (await sales.actions.list(deal.code, { sort: 'actor', order: 'asc' })).map((a) => a.id)
      const desc = (await sales.actions.list(deal.code, { sort: 'actor', order: 'desc' })).map((a) => a.id)

      expect(asc).toEqual([newer.id, older.id])
      expect(desc).toEqual([newer.id, older.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('answers 404 for the list of an unknown deal', async () => {
      const sales = await make('sales')

      await expectRejects(sales.actions.list('20000101-ZZZZ', {}), 404)
    })
  })
}
