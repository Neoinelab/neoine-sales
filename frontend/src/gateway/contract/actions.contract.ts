/**
 * Action 계약. mock과 실제 서버가 같은 결과를 내야 한다.
 * 호출마다 고유한 Deal을 만들고 스스로 지운다(Deal 삭제가 Action을 함께 지운다). 시드에 기대지 않는다.
 * 다른 사용자 세션이 필요한 403 사례는 mock 단위 테스트가 맡는다(여기서는 admin의 타인 Action 수정·삭제만).
 */

import { describe, expect, it } from 'vitest'
import type { ActionInput, DealInput } from '../../shared/model/types'
import { addDays, datePart } from '../../shared/model/dates'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID, anyVendorId } from './support'

const REVENUE_NEEDED = 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'
const ACTED_REVERSED = '수행일 범위의 시작은 끝보다 늦을 수 없습니다.'
const DUE_REVERSED = 'Due Date 범위의 시작은 끝보다 늦을 수 없습니다.'

export async function newDeal(gateway: Gateway) {
  const me = await gateway.auth.me()
  const input: DealInput = {
    name: unique('deal'),
    ownerId: me.id,
    vendorId: await anyVendorId(gateway),
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

/** 서버 업무 날짜에 일수를 더한다. 응답의 `actedOn`은 이미 시각 없는 서버 업무 날짜다(브라우저 시간대와 무관). */
function localDay(iso: string, plusDays = 0): string {
  return addDays(datePart(iso), plusDays)
}

export function actionsContract(make: MakeGateway): void {
  describe('actions 계약', () => {
    // 요청자 이름으로 현재 Status/Forecast와 서버 시각을 담아 등록한다.
    // 테스트 코드: AC-090
    it('registers an action as the requester with the current status, forecast and a server time', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await newDeal(sales)

      // when: Action을 등록한다
      const created = await sales.actions.create(deal.code, action({ memo: '메모' }))

      // then: 요청자·등록 시점 값이 채워지고 서버 시각이 있다
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
      expect(created.actedOn).toMatch(/^\d{4}-\d{2}-\d{2}$/) // 수행일은 시각 없는 날짜다
      // then: 목록에 그 Action 하나뿐이다
      expect(await sales.actions.list(deal.code, {})).toEqual([created])
      await sales.deals.remove(deal.code, deal.code)
    })

    // user는 등록할 수 없다(403).
    // 테스트 코드: AC-090
    it('refuses the user role to register with 403', async () => {
      // given: sales가 만든 Deal과 user 세션
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const user = await make('user')

      // when·then: user가 등록하면 403이다
      await expectRejects(user.actions.create(deal.code, action()), 403)

      const again = await make('sales')
      // then: Action이 없다
      expect(await again.actions.list(deal.code, {})).toEqual([])
      await again.deals.remove(deal.code, deal.code)
    })

    // Deal 확인 → 진행사항/Next Action → Due Date 규칙 순서이고 아무것도 저장하지 않는다.
    // 테스트 코드: AC-090
    it('checks the deal first, then "progress or Next Action", then the Due Date rules, storing nothing', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when·then: 없는 Deal이면 404다
      await expectRejects(sales.actions.create('20000101-ZZZZ', action({ progress: ' ' })), 404)
      // when·then: 내용이 비면 진행사항 문구 422다
      await expectRejects(sales.actions.create(deal.code, action({ progress: ' ', nextAction: ' ', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')
      // when·then: Due가 없으면 Due 필수 422다
      await expectRejects(sales.actions.create(deal.code, action({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
      // when·then: Next Action 없이 Due가 있으면 Due 금지 422다
      await expectRejects(sales.actions.create(deal.code, action({ nextAction: ' ' })), 422, 'Next Action 없이 Due Date를 입력할 수 없습니다.')

      // then: 저장된 Action이 없다
      expect(await sales.actions.list(deal.code, {})).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 지난 Due Date를 받고 세 텍스트의 공백을 지운다.
    // 테스트 코드: AC-090
    it('accepts a past due date and trims the three texts', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when: 지난 Due와 공백이 낀 텍스트로 등록한다
      const created = await sales.actions.create(deal.code, action({ dueDate: '2000-01-01', progress: '  진행  ', nextAction: ' 다음 ', memo: '  메모  ' }))

      // then: 공백이 지워지고 Due가 그대로다
      expect(created).toMatchObject({ dueDate: '2000-01-01', progress: '진행', nextAction: '다음', memo: '메모' })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 5,000/5,000/20,000자 텍스트를 잘림 없이 저장한다.
    // 테스트 코드: AC-090
    it('saves 5,000 / 5,000 / 20,000 character texts in full (no length limit)', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const progress = '가'.repeat(5000)
      const nextAction = '나'.repeat(5000)
      const memo = '다'.repeat(20000)

      // when: 긴 텍스트로 등록한다
      const created = await sales.actions.create(deal.code, action({ progress, nextAction, memo }))

      // then: 응답과 목록 모두 잘리지 않는다
      expect(created).toMatchObject({ progress, nextAction, memo })
      expect((await sales.actions.list(deal.code, {}))[0]).toMatchObject({ progress, nextAction, memo })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 최신 Action이 Deal 요약이 되고 Memo 부분이 있는 이력 1건이 남는다.
    // 테스트 코드: AC-090
    it('puts the latest action in the deal summary and writes one history entry with the Memo part', async () => {
      // given: sales와 새 Deal·이력 건수
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const baseline = (await sales.history.list(deal.code, {})).length

      // when: Memo가 있는 Action을 등록한다
      await sales.actions.create(deal.code, action({ memo: '메모' }))

      // then: Deal Next Action이 새 Action의 것이다
      const read = await sales.deals.get(deal.code)
      expect(read.nextAction).toEqual({ text: '견적 재전달', dueDate: '2026-12-01', status: 'open' })
      // then: 이력이 1건 늘고 "등록: <요약>"이다
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

    // Memo가 비면 이력 요약에 Memo 부분이 없다.
    // 테스트 코드: AC-090
    it('leaves out the Memo part of the history summary when the memo is empty', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when: Memo 없이 등록한다
      await sales.actions.create(deal.code, action())

      // then: 이력 요약에 Memo 부분이 없다
      expect((await sales.history.list(deal.code, {}))[0]?.after).toBe('등록: 미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-12-01)')
      await sales.deals.remove(deal.code, deal.code)
    })

    // 긴 이력 요약은 1,000자로 잘리고 Action 원문은 그대로다.
    // 테스트 코드: AC-090
    it('clips a long history summary to 1,000 characters ending with an ellipsis, keeping the action whole', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const progress = '가'.repeat(2000)

      // when: 진행사항 2,000자로 등록한다
      const created = await sales.actions.create(deal.code, action({ progress }))

      // then: 이력은 1,000자에서 "…"로 끝나고 원문은 그대로다
      const after = (await sales.history.list(deal.code, {}))[0]?.after ?? ''
      expect(Array.from(after)).toHaveLength(1000)
      expect(after.endsWith('…')).toBe(true)
      expect(created.progress).toBe(progress)
      await sales.deals.remove(deal.code, deal.code)
    })

    // 매출 없이 종결하는 등록은 거절되고 아무것도 저장되지 않는다.
    // 테스트 코드: AC-090
    it('refuses to close with an action when the actual revenue is missing and stores nothing', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when·then: 매출 답 없이 계약완료로 바꾸며 등록하면 422다
      await expectRejects(
        sales.actions.create(deal.code, action({ statusChanges: [{ change: { field: 'statusKey', value: 'contract_completed' } }] })),
        422,
        REVENUE_NEEDED,
      )

      // then: Action 없음, Deal 그대로다
      expect(await sales.actions.list(deal.code, {})).toEqual([])
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 동반 변경은 Deal과 함께 저장되고 Action에는 변경 뒤 값이 저장된다.
    // 테스트 코드: AC-090
    it('changes the deal together with the action and stores the post-change status and forecast', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when: 매출 답과 함께 계약완료로 바꾸며 등록한다
      const created = await sales.actions.create(
        deal.code,
        action({
          statusChanges: [{
            change: { field: 'statusKey', value: 'contract_completed' },
            resolution: { revenueAmount: 5_000_000, revenueDate: '2026-10-15' },
          }],
        }),
      )

      // then: 스냅숏이 계약완료·Won이다
      expect(created).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
      // then: Deal도 같은 값이다
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 5_000_000 })
      // then: 이력에 Action·Status·Forecast 줄이 있다
      const history = await sales.history.list(deal.code, {})
      expect(history[0]?.category).toBe('action')
      expect(history.slice(0, 8).map((h) => h.category)).toEqual(expect.arrayContaining(['status', 'forecast']))
      // 정리: Won(완료)이 된 Deal은 admin만 지울 수 있다(DD-R41).
      await (await make('admin')).deals.remove(deal.code, deal.code)
    })

    // 현재와 같은 Status를 요청하면 Action만 등록된다.
    // 테스트 코드: AC-090
    it('registers only the action when the requested status equals the current one', async () => {
      // given: sales와 새 Deal·이력 건수
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const baseline = (await sales.history.list(deal.code, {})).length

      // when: 현재 Status와 같은 값으로 바꾸며 등록한다
      const created = await sales.actions.create(deal.code, action({ statusChanges: [{ change: { field: 'statusKey', value: 'prospecting' } }] }))

      // then: 스냅숏은 그대로이고 이력은 Action 1건만 늘었다
      expect(created).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      expect(await sales.history.list(deal.code, {})).toHaveLength(baseline + 1)
      await sales.deals.remove(deal.code, deal.code)
    })

    // 나중의 Deal 변경과 Action 수정에도 Action의 Status/Forecast는 그대로다.
    // 테스트 코드: AC-090
    it('keeps the status and forecast of an action when the deal changes later or the action is edited', async () => {
      // given: 다른 Forecast 코드와 sales의 Action
      const admin = await make('admin')
      const other = (await admin.codes.list('forecast')).find((c) => c.outcome === 'open' && c.key !== 'pipeline')
      if (!other) throw new Error('다른 Forecast 코드가 필요합니다.')
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())

      // when: Deal Forecast를 바꾼 뒤 Action을 고친다
      await sales.deals.applyChange(deal.code, { change: { field: 'forecastKey', value: other.key } })
      const edited = await sales.actions.update(created.id, action({ progress: '수정' }))

      // then: 스냅숏·수행일시·담당자가 그대로다
      expect(edited).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline', actedOn: created.actedOn, actor: created.actor })
      expect((await sales.actions.list(deal.code, {}))[0]).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 실제 변경은 수정 전후 이력을 남기고 같은 내용 수정은 아무것도 남기지 않는다.
    // 테스트 코드: AC-090
    it('writes before and "수정: " after on a real change and nothing on an unchanged edit', async () => {
      // given: sales와 Action·이력
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const afterCreate = await sales.history.list(deal.code, {})

      // when: 공백만 다른 내용으로 고친다
      await sales.actions.update(created.id, action({ progress: `  ${created.progress}  ` }))
      // then: 이력이 그대로다
      expect(await sales.history.list(deal.code, {})).toEqual(afterCreate)

      // when: 유형·진행사항·Memo를 바꿔 고친다
      await sales.actions.update(created.id, action({ type: { name: '통화' }, progress: '전화', memo: '메모' }))
      const history = await sales.history.list(deal.code, {})
      // then: 이력이 1건 늘고 변경 전·후 요약이 있다
      expect(history).toHaveLength(afterCreate.length + 1)
      expect(history[0]).toMatchObject({
        category: 'action',
        before: '미팅 · 고객사 방문 / Next Action: 견적 재전달 (Due 2026-12-01)',
        after: '수정: 통화 · 전화 / Next Action: 견적 재전달 (Due 2026-12-01) / Memo: 메모',
      })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 수정도 같은 순서로 검증하고 없는 Action은 404다.
    // 테스트 코드: AC-090
    it('validates an edit in the same order and answers 404 for an unknown action', async () => {
      // given: sales와 Action
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())

      // when·then: 내용이 비면 진행사항 문구 422다
      await expectRejects(sales.actions.update(created.id, action({ progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')
      // when·then: Due가 없으면 Due 필수 422다
      await expectRejects(sales.actions.update(created.id, action({ dueDate: '' })), 422, 'Due Date를 입력하세요.')
      // when·then: Next Action 없이 Due가 있으면 Due 금지 422다
      await expectRejects(sales.actions.update(created.id, action({ nextAction: '', dueDate: '2026-12-01' })), 422, 'Next Action 없이 Due Date를 입력할 수 없습니다.')
      // when·then: 없는 Action이면 404다
      await expectRejects(sales.actions.update(NO_SUCH_ID, action()), 404, 'Action을 찾을 수 없습니다.')

      await sales.deals.remove(deal.code, deal.code)
    })

    // admin은 sales의 Action을 고치고 지우며 변경자는 admin이다.
    // 테스트 코드: AC-090
    it('lets admin edit and delete the action of a sales, logging admin as the changer', async () => {
      // given: sales의 Action과 admin 세션
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const admin = await make('admin')
      const adminId = (await admin.auth.me()).id

      // when: admin이 고친다
      const edited = await admin.actions.update(created.id, action({ progress: '관리자 수정' }))
      // then: 담당자는 그대로이고 이력 변경자는 admin이다
      expect(edited).toMatchObject({ progress: '관리자 수정', actor: created.actor })
      expect((await admin.history.list(deal.code, {}))[0]).toMatchObject({ category: 'action', by: { id: adminId } })

      // when: admin이 지운다
      await admin.actions.remove(created.id)
      // then: Action이 사라지고 이력 "삭제"의 변경자는 admin이다
      expect(await admin.actions.list(deal.code, {})).toEqual([])
      expect((await admin.history.list(deal.code, {}))[0]).toMatchObject({ after: '삭제', by: { id: adminId } })
      await admin.deals.remove(deal.code, deal.code)
    })

    // 최신 Action을 지우면 Deal의 Next Action이 이전 Action으로 돌아간다.
    // 테스트 코드: AC-090
    it('moves the deal next action back to the previous action when the latest one is deleted', async () => {
      // given: sales와 Next Action이 있는 Action 두 건
      const sales = await make('sales')
      const deal = await newDeal(sales)
      await sales.actions.create(deal.code, action({ nextAction: '첫 Next', dueDate: '2026-12-01' }))
      const latest = await sales.actions.create(deal.code, action({ nextAction: '둘째 Next', dueDate: '2026-12-09' }))
      expect((await sales.deals.get(deal.code)).nextAction).toEqual({ text: '둘째 Next', dueDate: '2026-12-09', status: 'open' })

      // when: 최신 Action을 지운다
      await sales.actions.remove(latest.id)

      // then: Deal Next Action이 이전 Action의 것이다
      expect((await sales.deals.get(deal.code)).nextAction).toEqual({ text: '첫 Next', dueDate: '2026-12-01', status: 'open' })
      await sales.deals.remove(deal.code, deal.code)
    })

    // 없는 Action의 삭제는 404다.
    // 테스트 코드: AC-090
    it('answers 404 when deleting an unknown action', async () => {
      // given: sales
      const sales = await make('sales')

      // when·then: 없는 id를 지우면 404다
      await expectRejects(sales.actions.remove(NO_SUCH_ID), 404, 'Action을 찾을 수 없습니다.')
    })

    // 수행일 조건은 서버 달력 날짜 단위이고 양끝을 포함한다.
    // 테스트 코드: NA-029
    it('수행일 조건은 달력 날짜 단위로 양끝을 포함해 거른다', async () => {
      // given: Action 하나가 있는 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const day = localDay(created.actedOn)
      const ids = async (from: string, to: string) => (await sales.actions.list(deal.code, { actedFrom: from, actedTo: to })).map((a) => a.id)

      // when·then: 수행일을 끝으로 하는 범위, 시작으로 하는 범위는 Action이 나온다
      expect(await ids(day, day)).toEqual([created.id])
      expect(await ids(localDay(created.actedOn, -3), day)).toEqual([created.id])
      expect(await ids(day, localDay(created.actedOn, 3))).toEqual([created.id])
      // when·then: 수행일 앞뒤로 벗어난 범위는 비어 있다
      expect(await ids(localDay(created.actedOn, 1), localDay(created.actedOn, 2))).toEqual([])
      expect(await ids(localDay(created.actedOn, -2), localDay(created.actedOn, -1))).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    // Due Date 범위는 양끝을 포함하고 밖의 날짜는 제외한다.
    // 테스트 코드: NA-030
    it('Due Date 범위는 양끝을 포함해 거른다', async () => {
      // given: Due Date가 12-24인 Action이 있는 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action({ dueDate: '2026-12-24' }))
      const ids = async (from?: string, to?: string) => (await sales.actions.list(deal.code, { dueFrom: from, dueTo: to })).map((a) => a.id)

      // when·then: 12-24 하루 범위는 Action이 나오고 12-25 이후, 12-23 이전 범위는 비어 있다
      expect(await ids('2026-12-24', '2026-12-24')).toEqual([created.id])
      expect(await ids('2026-12-25', undefined)).toEqual([])
      expect(await ids(undefined, '2026-12-23')).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 거꾸로 된 수행일 범위와 Due Date 범위는 각자의 문구로 422다.
    // 테스트 코드: NA-031
    it('거꾸로 된 수행일 범위와 Due Date 범위는 각자의 문구로 422다', async () => {
      // given: Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when·then: 시작이 끝보다 늦은 수행일 범위는 수행일 문구의 422다
      await expectRejects(sales.actions.list(deal.code, { actedFrom: '2026-10-20', actedTo: '2026-10-01' }), 422, ACTED_REVERSED)
      // when·then: 시작이 끝보다 늦은 Due Date 범위는 Due Date 문구의 422다
      await expectRejects(sales.actions.list(deal.code, { dueFrom: '2026-10-20', dueTo: '2026-10-01' }), 422, DUE_REVERSED)
      await sales.deals.remove(deal.code, deal.code)
    })

    // 유형·검색어(진행사항·Next Action·Memo, 대소문자 무시)·담당자 조건은 AND로 결합된다.
    // 테스트 코드: NA-023, NA-026
    it('유형·검색어·담당자 조건은 AND로 결합되고 검색어는 대소문자를 구분하지 않는다', async () => {
      // given: 유형과 진행사항이 다른 Action 셋이 있는 Deal(하나는 긴 Memo에 NEEDLE)
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await newDeal(sales)
      const call = await sales.actions.create(deal.code, action({ type: { name: '통화' }, progress: 'Alpha 통화' }))
      await sales.actions.create(deal.code, action({ type: { name: '미팅' }, progress: 'Alpha 미팅' }))
      const viaMemo = await sales.actions.create(deal.code, action({ type: { name: '이메일' }, memo: `긴 메모 ${'x'.repeat(3000)} NEEDLE 끝` }))
      const ids = async (q: Parameters<Gateway['actions']['list']>[1]) => (await sales.actions.list(deal.code, q)).map((a) => a.id)
      const types = await sales.actionTypes.list()
      const typeId = (name: string) => types.find((t) => t.name === name)?.id ?? NO_SUCH_ID

      // when·then: 유형+검색어는 둘 다 맞는 Action만, 검색어는 Memo도 대소문자 무시로 찾는다
      expect(await ids({ typeId: typeId('통화'), keyword: 'alpha' })).toEqual([call.id])
      expect(await ids({ keyword: 'needle' })).toEqual([viaMemo.id])
      // when·then: 담당자+유형은 둘 다 맞는 Action만, 없는 담당자는 빈 목록이다
      expect(await ids({ actorId: me.id, typeId: typeId('이메일') })).toEqual([viaMemo.id])
      expect(await ids({ actorId: NO_SUCH_ID })).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })

    // Due Date 정렬은 양방향이고 정렬을 정하지 않으면 최신 수행이 먼저다.
    // 테스트 코드: NA-039
    it('Due Date 정렬은 양방향이고 기본 순서는 최신 수행이 먼저다', async () => {
      // given: Due Date가 서로 다른 Action 셋이 있는 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const late = await sales.actions.create(deal.code, action({ dueDate: '2026-12-30' }))
      const early = await sales.actions.create(deal.code, action({ dueDate: '2026-12-02' }))
      const middle = await sales.actions.create(deal.code, action({ dueDate: '2026-12-15' }))

      // when: Due Date 오름차순·내림차순과 기본 순서로 목록을 읽는다
      const byDue = (await sales.actions.list(deal.code, { sort: 'dueDate', order: 'asc' })).map((a) => a.id)
      const byDueDesc = (await sales.actions.list(deal.code, { sort: 'dueDate', order: 'desc' })).map((a) => a.id)
      const byDefault = (await sales.actions.list(deal.code, {})).map((a) => a.id)

      // then: 오름차순은 이른 Due Date부터, 내림차순은 그 반대, 기본은 최신 수행 순이다
      expect(byDue).toEqual([early.id, middle.id, late.id])
      expect(byDueDesc).toEqual([late.id, middle.id, early.id])
      expect(byDefault).toEqual([middle.id, early.id, late.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 유형 정렬은 유형 이름을 대소문자 구분 없이 양방향으로 비교한다.
    // 테스트 코드: NA-041
    it('유형 정렬은 유형 이름을 대소문자 구분 없이 양방향으로 비교한다', async () => {
      // given: 유형 이름이 Beta·통화·alpha·미팅인 Action이 있는 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const beta = await sales.actions.create(deal.code, action({ type: { name: 'Beta' } }))
      const call = await sales.actions.create(deal.code, action({ type: { name: '통화' } }))
      const alpha = await sales.actions.create(deal.code, action({ type: { name: 'alpha' } }))
      const meeting = await sales.actions.create(deal.code, action({ type: { name: '미팅' } }))
      const ids = async (order: 'asc' | 'desc') => (await sales.actions.list(deal.code, { sort: 'type', order })).map((a) => a.id)

      // when·then: 오름차순은 alpha < Beta < 미팅 < 통화이고 내림차순은 그 반대다
      expect(await ids('asc')).toEqual([alpha.id, beta.id, meeting.id, call.id])
      expect(await ids('desc')).toEqual([call.id, meeting.id, beta.id, alpha.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 같은 담당자의 Action은 담당자 정렬을 어느 방향으로 해도 최신 수행이 먼저다.
    it('같은 담당자 안에서는 담당자 정렬의 방향과 관계없이 최신 수행이 먼저다', async () => {
      // given: 같은 담당자가 먼저·나중에 등록한 Action 둘이 있는 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const older = await sales.actions.create(deal.code, action({ progress: '먼저' }))
      const newer = await sales.actions.create(deal.code, action({ progress: '나중' }))

      // when: 담당자 오름차순·내림차순으로 목록을 읽는다
      const asc = (await sales.actions.list(deal.code, { sort: 'actor', order: 'asc' })).map((a) => a.id)
      const desc = (await sales.actions.list(deal.code, { sort: 'actor', order: 'desc' })).map((a) => a.id)

      // then: 두 방향 모두 나중에 등록한 Action이 먼저다
      expect(asc).toEqual([newer.id, older.id])
      expect(desc).toEqual([newer.id, older.id])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 없는 Deal의 목록은 404다.
    // 테스트 코드: AC-090
    it('answers 404 for the list of an unknown deal', async () => {
      // given: sales
      const sales = await make('sales')

      // when·then: 없는 Deal의 목록을 읽으면 404다
      await expectRejects(sales.actions.list('20000101-ZZZZ', {}), 404)
    })

    // 수행일 범위: 오늘은 받고, 내일과 Deal 등록일 전날은 문구와 함께 거절한다(새 Deal은 오늘 등록되므로 오늘이 등록일이다).
    // 테스트 코드: AC-110
    it('accepts today as the performed day and refuses tomorrow and the day before the registration day', async () => {
      // given: sales와 오늘 등록한 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const today = localDay(deal.createdAt)

      // when: 수행일을 오늘로 지정해 등록한다
      const created = await sales.actions.create(deal.code, action({ actedOn: today }))
      // then: 수행일은 오늘 날짜다
      expect(localDay(created.actedOn)).toBe(today)

      // when·then: 내일을 지정하면 422 문구로 거절된다
      await expectRejects(
        sales.actions.create(deal.code, action({ actedOn: localDay(deal.createdAt, 1) })),
        422,
        '수행일은 오늘 이후로 지정할 수 없습니다.',
      )
      // when·then: 등록일 전날을 지정하면 등록일이 든 문구로 거절된다
      await expectRejects(
        sales.actions.create(deal.code, action({ actedOn: localDay(deal.createdAt, -1) })),
        422,
        `수행일은 Deal 등록일(${today}) 이전으로 지정할 수 없습니다.`,
      )
      // then: Action은 처음 등록한 하나뿐이다
      expect(await sales.actions.list(deal.code, {})).toEqual([created])
      await sales.deals.remove(deal.code, deal.code)
    })
  })
}
