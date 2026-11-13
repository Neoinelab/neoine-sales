/**
 * Deal 등록·수정의 BANT 선택 객체(`{id}` | `{name}` | null) 계약. mock과 실제 서버가 같은 결과를 내야 한다.
 * 만든 Label과 Deal은 스스로 지운다.
 */

import { describe, expect, it } from 'vitest'
import type { DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID, anyVendorId } from './support'

const NONE = { budget: null, authority: null, need: null, timeline: null } as const

async function dealInput(gateway: Gateway, over: Partial<DealInput> = {}): Promise<DealInput> {
  const me = await gateway.auth.me()
  return {
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
    bant: NONE,
    ...over,
  }
}

export function dealBantContract(make: MakeGateway): void {
  describe('Deal BANT 선택 객체 계약', () => {
    it('id로 고른 Label은 유지하고 null은 선택 안 함으로 본다', async () => {
      const sales = await make('sales')
      // given: 기본 예산 Label
      const label = (await sales.labels.list()).find((l) => l.category === 'budget' && l.isDefault)

      // when: Label id를 BANT 예산에 넣어 Deal을 등록한다
      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { id: label?.id ?? NO_SUCH_ID } } }))

      // then: 예산은 그 Label id이고 나머지는 null이다
      expect(deal.bant).toEqual({ ...NONE, budget: label?.id })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('없는 id와 다른 구분의 id는 Label 문구와 함께 거절한다', async () => {
      const sales = await make('sales')
      // given: need 구분의 기본 Label
      const need = (await sales.labels.list()).find((l) => l.category === 'need' && l.isDefault)

      // when·then: 없는 id와 다른 구분(need)의 id로 예산을 등록하면 Label 문구와 함께 422다
      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { id: NO_SUCH_ID } } })), 422, 'BANT Label이 올바르지 않습니다.')
      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { id: need?.id ?? NO_SUCH_ID } } })), 422, 'BANT Label이 올바르지 않습니다.')
    })

    it('대소문자·공백만 다른 같은 구분 이름은 Label을 새로 만들지 않고 재사용한다', async () => {
      const sales = await make('sales')
      // given: 현재 Label 수
      const before = (await sales.labels.list()).length

      // when: 기본 Label과 공백·대소문자만 다른 이름으로 Deal을 등록한다
      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { name: '  단독 예산 확보 ' } } }))

      // then: Label 수가 늘지 않고 기존 Label 이름이 연결된다 (끝에 Deal을 지운다)
      const labels = await sales.labels.list()
      expect(labels).toHaveLength(before)
      expect(labels.find((l) => l.id === deal.bant.budget)?.name).toBe('단독 예산 확보')
      await sales.deals.remove(deal.code, deal.code)
    })

    it('없는 이름은 등록자가 만든 그 구분의 새 Label로 만든다', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      // given: 존재하지 않는 이름
      const name = unique('plan')

      // when: 그 이름을 need에 넣어 Deal을 등록한다
      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, need: { name: ` ${name} ` } } }))

      // then: 등록자가 만든 need 구분 새 Label이 사용 1건으로 생긴다 (끝에 정리한다)
      const created = (await sales.labels.list()).find((l) => l.id === deal.bant.need)
      expect(created).toMatchObject({ category: 'need', name, isDefault: false, usageCount: 1, createdBy: { id: me.id } })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).labels.remove(created?.id ?? NO_SUCH_ID)
    })

    it('다른 구분에 있는 같은 이름은 재사용하지 않고 새 Label을 만든다', async () => {
      const sales = await make('sales')
      // when: 다른 구분(budget)에 있는 이름을 authority에 넣어 Deal을 등록한다
      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, authority: { name: '단독 예산 확보' } } }))

      // then: authority 구분의 새 Label이 만들어진다 (끝에 정리한다)
      const created = (await sales.labels.list()).find((l) => l.id === deal.bant.authority)
      expect(created).toMatchObject({ category: 'authority', name: '단독 예산 확보', isDefault: false })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).labels.remove(created?.id ?? NO_SUCH_ID)
    })

    it('이름에는 Label 이름 규칙을 적용한다', async () => {
      const sales = await make('sales')

      // when·then: 공백만 있는 이름과 51자 이름은 Label 문구와 함께 422다
      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, need: { name: '   ' } } })), 422, 'Label 이름을 입력하세요.')
      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, need: { name: 'x'.repeat(51) } } })), 422, 'Label 이름은 50자 이내로 입력하세요.')
    })

    it('뒤 검증이 실패하면 Label을 만들지 않는다', async () => {
      const sales = await make('sales')
      // given: 아직 없는 Label 이름
      const name = unique('ghost')

      // when: 새 Label 이름과 잘못된 다른 입력으로 등록을 시도한다
      await expectRejects(sales.deals.create(await dealInput(sales, { bant: { ...NONE, timeline: { name } }, procurement: 'a'.repeat(501) })), 422)

      // then: 등록이 422로 거절되고 새 Label은 만들어지지 않는다
      expect((await sales.labels.list()).some((l) => l.name === name)).toBe(false)
    })

    it('이름으로 BANT를 수정하면 이력에 새 Label 이름이 남는다', async () => {
      const sales = await make('sales')
      // given: Deal 하나와 새 Label 이름
      const deal = await sales.deals.create(await dealInput(sales))
      const name = unique('later')

      // when: 이름으로 예산을 수정한다
      const patched = await sales.deals.update(deal.code, { bant: { ...NONE, budget: { name } } })

      // then: bant 이력이 1건이고 새 Label 이름을 담는다 (끝에 정리한다)
      const history = (await sales.history.list(deal.code, {})).filter((h) => h.category === 'bant')
      expect(history).toHaveLength(1)
      expect(history[0]?.after).toContain(name)
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).labels.remove(patched.bant.budget ?? NO_SUCH_ID)
    })

    it('바뀌지 않은 BANT 구분은 이력을 남기지 않는다', async () => {
      // given: 예산 Label이 있는 Deal과 현재 이력 수
      const sales = await make('sales')
      const label = (await sales.labels.list()).find((l) => l.category === 'budget' && l.isDefault)
      const deal = await sales.deals.create(await dealInput(sales, { bant: { ...NONE, budget: { id: label?.id ?? NO_SUCH_ID } } }))
      const base = (await sales.history.list(deal.code, {})).length

      // when: 같은 Label id로 수정한다
      await sales.deals.update(deal.code, { bant: { ...NONE, budget: { id: label?.id ?? NO_SUCH_ID } } })

      // then: 이력 수가 그대로다
      expect(await sales.history.list(deal.code, {})).toHaveLength(base)
      await sales.deals.remove(deal.code, deal.code)
    })
  })
}
