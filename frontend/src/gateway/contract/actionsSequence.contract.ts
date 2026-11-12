/**
 * Action 등록의 두 변경(`statusChanges`) 계약. mock과 실제 서버가 같은 결과를 내야 한다.
 * 호출마다 고유한 Deal을 만들고 스스로 지운다. 시드에 기대지 않는다.
 */

import { describe, expect, it } from 'vitest'
import { SYNC_CONFLICT_MESSAGE } from '../../shared/model/sync'
import type { ActionInput, DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway } from './support'

async function newDeal(gateway: Gateway) {
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

const action = (over: Partial<ActionInput> = {}): ActionInput => ({
  type: { name: '미팅' },
  progress: '고객사 방문',
  nextAction: '견적 재전달',
  dueDate: '2026-12-01',
  memo: '',
  ...over,
})

export function actionsSequenceContract(make: MakeGateway): void {
  describe('actions 계약: Status·Forecast 두 변경', () => {
    // 두 변경을 순서대로 적용하고 Action과 Deal에 변경 뒤 값을 저장한다.
    // 테스트 코드: AC-090
    it('applies both changes in order and stores the post-change values on the action and the deal', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when: Status 제품소개, Forecast Best로 바꾸며 등록한다
      const created = await sales.actions.create(
        deal.code,
        action({
          statusChanges: [
            { change: { field: 'statusKey', value: 'introduction' } },
            { change: { field: 'forecastKey', value: 'best' } },
          ],
        }),
      )

      // then: Action과 Deal이 제품소개·Best이다
      expect(created).toMatchObject({ statusKey: 'introduction', forecastKey: 'best' })
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'introduction', forecastKey: 'best' })
      // then: 이력은 Action, Forecast, Status 순서다
      const history = await sales.history.list(deal.code, {})
      expect(history.slice(0, 3).map((h) => h.category)).toEqual(['action', 'forecast', 'status'])
      await sales.deals.remove(deal.code, deal.code)
    })

    // 첫 변경을 뒤집는 두 번째 변경은 422이고 아무것도 저장되지 않는다.
    // 테스트 코드: AC-090
    it('rejects a second change that overrides the first and stores nothing', async () => {
      // given: sales와 새 Deal·이력 건수
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const baseline = (await sales.history.list(deal.code, {})).length

      // when·then: Status 제품소개 뒤 Forecast Won은 충돌 422다
      await expectRejects(
        sales.actions.create(
          deal.code,
          action({
            statusChanges: [
              { change: { field: 'statusKey', value: 'introduction' } },
              {
                change: { field: 'forecastKey', value: 'won' },
                resolution: { revenueAmount: 5_000_000, revenueDate: '2026-10-15' },
              },
            ],
          }),
        ),
        422,
        SYNC_CONFLICT_MESSAGE,
      )

      // then: Action·Deal·이력이 그대로다
      expect(await sales.actions.list(deal.code, {})).toEqual([])
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      expect(await sales.history.list(deal.code, {})).toHaveLength(baseline)
      await sales.deals.remove(deal.code, deal.code)
    })

    // 매출 판정 전에 모든 코드의 존재를 확인하고 아무것도 저장하지 않는다.
    // 테스트 코드: AC-090
    it('checks that every code exists before judging revenue and stores nothing', async () => {
      // given: sales와 새 Deal
      const sales = await make('sales')
      const deal = await newDeal(sales)

      // when·then: 매출 없는 계약완료 뒤 없는 Forecast 코드는 코드 없음 422다
      await expectRejects(
        sales.actions.create(
          deal.code,
          action({
            statusChanges: [
              { change: { field: 'statusKey', value: 'contract_completed' } },
              { change: { field: 'forecastKey', value: 'no_such_forecast' } },
            ],
          }),
        ),
        422,
        '존재하지 않는 코드입니다.',
      )

      // then: Action·Deal이 그대로다
      expect(await sales.actions.list(deal.code, {})).toEqual([])
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      await sales.deals.remove(deal.code, deal.code)
    })
  })
}
