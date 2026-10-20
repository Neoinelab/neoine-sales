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
    solutionId: null,
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
    it('applies both changes in order and stores the post-change values on the action and the deal', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      const created = await sales.actions.create(
        deal.code,
        action({
          statusChanges: [
            { change: { field: 'statusKey', value: 'introduction' } },
            { change: { field: 'forecastKey', value: 'best' } },
          ],
        }),
      )

      expect(created).toMatchObject({ statusKey: 'introduction', forecastKey: 'best' })
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'introduction', forecastKey: 'best' })
      const history = await sales.history.list(deal.code, {})
      expect(history.slice(0, 3).map((h) => h.category)).toEqual(['action', 'forecast', 'status'])
      await sales.deals.remove(deal.code, deal.code)
    })

    it('rejects a second change that overrides the first and stores nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const baseline = (await sales.history.list(deal.code, {})).length

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

      expect(await sales.actions.list(deal.code, {})).toEqual([])
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      expect(await sales.history.list(deal.code, {})).toHaveLength(baseline)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('checks that every code exists before judging revenue and stores nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

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

      expect(await sales.actions.list(deal.code, {})).toEqual([])
      expect(await sales.deals.get(deal.code)).toMatchObject({ statusKey: 'prospecting', forecastKey: 'pipeline' })
      await sales.deals.remove(deal.code, deal.code)
    })
  })
}
