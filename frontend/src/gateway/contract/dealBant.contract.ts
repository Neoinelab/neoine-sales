/**
 * Deal 등록·수정의 BANT 선택 객체(`{id}` | `{name}` | null) 계약(AC-17~22). mock과 실제 서버가 같은 결과를 내야 한다.
 * 만든 Label과 Deal은 스스로 지운다.
 */

import { describe, expect, it } from 'vitest'
import type { DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID } from './support'

const NONE = { budget: null, authority: null, need: null, timeline: null } as const

async function dealInput(gateway: Gateway, over: Partial<DealInput> = {}): Promise<DealInput> {
  const me = await gateway.auth.me()
  return {
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
    bant: NONE,
    ...over,
  }
}

export function dealBantContract(make: MakeGateway): void {
  describe('Deal BANT 선택 객체 계약', () => {
    it('keeps a label chosen by id and treats null as not selected', async () => {
      const sales = await make('sales')
      const label = (await sales.labels.list()).find((l) => l.category === 'budget' && l.isDefault)

      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { id: label?.id ?? NO_SUCH_ID } } }))

      expect(deal.bant).toEqual({ ...NONE, budget: label?.id })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('rejects an unknown id and an id of another category with the label message', async () => {
      const sales = await make('sales')
      const need = (await sales.labels.list()).find((l) => l.category === 'need' && l.isDefault)

      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { id: NO_SUCH_ID } } })), 422, 'BANT Label이 올바르지 않습니다.')
      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { id: need?.id ?? NO_SUCH_ID } } })), 422, 'BANT Label이 올바르지 않습니다.')
    })

    it('reuses a label of the same category by a name that differs in case, without adding one', async () => {
      const sales = await make('sales')
      const before = (await sales.labels.list()).length

      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { name: '  단독 예산 확보 ' } } }))

      const labels = await sales.labels.list()
      expect(labels).toHaveLength(before)
      expect(labels.find((l) => l.id === deal.bant.budget)?.name).toBe('단독 예산 확보')
      await sales.deals.remove(deal.code, deal.code)
    })

    it('creates a new label of that category by the requester for an unknown name', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      const name = unique('plan')

      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, need: { name: ` ${name} ` } } }))

      const created = (await sales.labels.list()).find((l) => l.id === deal.bant.need)
      expect(created).toMatchObject({ category: 'need', name, isDefault: false, usageCount: 1, createdBy: { id: me.id } })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).labels.remove(created?.id ?? NO_SUCH_ID)
    })

    it('creates a label for the same name in another category instead of reusing the other one', async () => {
      const sales = await make('sales')
      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, authority: { name: '단독 예산 확보' } } }))

      const created = (await sales.labels.list()).find((l) => l.id === deal.bant.authority)
      expect(created).toMatchObject({ category: 'authority', name: '단독 예산 확보', isDefault: false })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).labels.remove(created?.id ?? NO_SUCH_ID)
    })

    it('applies the label name rules to a name', async () => {
      const sales = await make('sales')

      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, need: { name: '   ' } } })), 422, 'Label 이름을 입력하세요.')
      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, need: { name: 'x'.repeat(51) } } })), 422, 'Label 이름은 50자 이내로 입력하세요.')
    })

    it('creates no label when a later validation fails', async () => {
      const sales = await make('sales')
      const name = unique('ghost')

      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, timeline: { name } }, procurement: 'a'.repeat(501) })), 422)

      expect((await sales.labels.list()).some((l) => l.name === name)).toBe(false)
    })

    it('records the bant change in the history with the new label name when patched by name', async () => {
      const sales = await make('sales')
      const deal = await sales.deals.create(await dealInput(sales))
      const name = unique('later')

      const patched = await sales.deals.update(deal.code, { bant: { ...NONE, budget: { name } } })

      const history = (await sales.history.list(deal.code, {})).filter((h) => h.category === 'bant')
      expect(history).toHaveLength(1)
      expect(history[0]?.after).toContain(name)
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).labels.remove(patched.bant.budget ?? NO_SUCH_ID)
    })

    it('records nothing for a bant category that does not change', async () => {
      const sales = await make('sales')
      const label = (await sales.labels.list()).find((l) => l.category === 'budget' && l.isDefault)
      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { id: label?.id ?? NO_SUCH_ID } } }))
      const base = (await sales.history.list(deal.code, {})).length

      await sales.deals.update(deal.code, { bant: { ...NONE, budget: { id: label?.id ?? NO_SUCH_ID } } })

      expect(await sales.history.list(deal.code, {})).toHaveLength(base)
      await sales.deals.remove(deal.code, deal.code)
    })
  })
}
