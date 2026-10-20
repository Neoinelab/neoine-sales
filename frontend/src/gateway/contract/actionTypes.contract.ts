/**
 * Action 유형 카탈로그와 Action의 유형 선택 객체(AC-1~16) 계약. mock과 실제 서버가 같은 결과를 내야 한다.
 * 이름은 호출마다 고유하게 만들고, 만든 유형은 스스로 지운다. 기본 유형 8개는 서버 시드와 같은 이름·순서다.
 */

import { describe, expect, it } from 'vitest'
import type { ActionInput, DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway } from './support'

const DEFAULTS = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타']
const DUPLICATE = '이미 있는 유형 이름입니다.'
const REQUIRED = '유형을 입력하세요.'
const TOO_LONG = '유형은 50자 이내로 입력하세요.'
const UNKNOWN = '선택한 유형이 없습니다. 목록에서 다시 선택하세요.'
const NO_SUCH_ID = '00000000-0000-4000-8000-000000000000'

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

export function actionTypesContract(make: MakeGateway): void {
  describe('actionTypes 계약', () => {
    it('lists the eight default types in order for every role, unused and without a creator', async () => {
      for (const role of ['admin', 'sales', 'user'] as const) {
        const { actionTypes } = await make(role)
        const defaults = (await actionTypes.list()).filter((t) => t.isDefault)

        expect(defaults.map((t) => t.name)).toEqual(DEFAULTS)
        expect(defaults.every((t) => t.createdBy === null)).toBe(true)
      }
    })

    it('puts custom types after the defaults', async () => {
      const admin = await make('admin')
      const created = await admin.actionTypes.create(unique('zz'))

      const list = await admin.actionTypes.list()

      expect(list.slice(0, 8).map((t) => t.name)).toEqual(DEFAULTS)
      expect(list.findIndex((t) => t.id === created.id)).toBeGreaterThanOrEqual(8)
      await admin.actionTypes.remove(created.id)
    })

    it('lets sales create a trimmed non-default type owned by the creator, and refuses the user role', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      const name = unique('webinar')

      const created = await sales.actionTypes.create(`  ${name}  `)

      expect(created).toMatchObject({ name, isDefault: false, usageCount: 0, createdBy: { id: me.id } })
      const user = await make('user')
      await expectRejects(user.actionTypes.create(unique('x')), 403)
      const admin = await make('admin')
      await admin.actionTypes.remove(created.id)
    })

    it('rejects blank and over-long names, and allows exactly 50 characters', async () => {
      const admin = await make('admin')

      await expectRejects(admin.actionTypes.create('   '), 422, REQUIRED)
      await expectRejects(admin.actionTypes.create('x'.repeat(51)), 422, TOO_LONG)
      const fifty = await admin.actionTypes.create(unique('f').padEnd(50, 'x'))
      expect(Array.from(fifty.name)).toHaveLength(50)
      await admin.actionTypes.remove(fifty.id)
    })

    it('rejects a duplicate name ignoring case and allows changing only the case of its own name', async () => {
      const admin = await make('admin')
      const name = unique('Demo')
      const created = await admin.actionTypes.create(name)

      await expectRejects(admin.actionTypes.create(name.toUpperCase()), 409, DUPLICATE)
      const recased = await admin.actionTypes.rename(created.id, name.toUpperCase())
      expect(recased.name).toBe(name.toUpperCase())
      await expectRejects(admin.actionTypes.rename(created.id, '미팅'), 409, DUPLICATE)
      await admin.actionTypes.remove(created.id)
    })

    it('lets only the admin rename and delete, and answers 404 for an unknown id', async () => {
      const admin = await make('admin')
      const created = await admin.actionTypes.create(unique('own'))
      const sales = await make('sales')

      await expectRejects(sales.actionTypes.rename(created.id, unique('new')), 403)
      await expectRejects(sales.actionTypes.remove(created.id), 403)
      const again = await make('admin')
      await expectRejects(again.actionTypes.rename(NO_SUCH_ID, unique('new')), 404)
      await expectRejects(again.actionTypes.remove(NO_SUCH_ID), 404)
      await again.actionTypes.remove(created.id)
    })

    it('counts the actions that use a type and refuses to delete it with the count', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const name = unique('used')
      await sales.actions.create(deal.code, action({ type: { name } }))
      await sales.actions.create(deal.code, action({ type: { name } }))
      const admin = await make('admin')
      const used = (await admin.actionTypes.list()).find((t) => t.name === name)

      expect(used?.usageCount).toBe(2)
      await expectRejects(admin.actionTypes.remove(used?.id ?? ''), 409, '사용 중인 유형은 삭제할 수 없습니다. (Action 2건)')
      expect((await admin.actionTypes.list()).some((t) => t.id === used?.id)).toBe(true)
      await admin.deals.remove(deal.code, deal.code)
      await admin.actionTypes.remove(used?.id ?? '')
    })
  })

  describe('Action 유형 선택 객체 계약', () => {
    it('uses a type chosen by id and answers with its id and current name', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const meeting = (await sales.actionTypes.list()).find((t) => t.name === '미팅')

      const created = await sales.actions.create(deal.code, action({ type: { id: meeting?.id ?? '' } }))

      expect(created).toMatchObject({ type: '미팅', typeId: meeting?.id })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('rejects an unknown type id with 422 and the re-select message', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      await expectRejects(sales.actions.create(deal.code, action({ type: { id: NO_SUCH_ID } })), 422, UNKNOWN)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('reuses an existing type for a name that differs only in case or spaces, without adding a type', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const before = (await sales.actionTypes.list()).length

      const created = await sales.actions.create(deal.code, action({ type: { name: ' 데모 ' } }))

      expect(created.type).toBe('데모')
      expect((await sales.actionTypes.list()).length).toBe(before)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('creates a new type for an unknown name in the same request, made by the requester', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await newDeal(sales)
      const name = unique('seminar')

      const created = await sales.actions.create(deal.code, action({ type: { name: `  ${name} ` } }))

      expect(created.type).toBe(name)
      const added = (await sales.actionTypes.list()).find((t) => t.id === created.typeId)
      expect(added).toMatchObject({ name, isDefault: false, usageCount: 1, createdBy: { id: me.id } })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).actionTypes.remove(created.typeId)
    })

    it('creates no type when the registration fails', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const name = unique('ghost')

      await expectRejects(sales.actions.create(deal.code, action({ type: { name }, progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')

      expect((await sales.actionTypes.list()).some((t) => t.name === name)).toBe(false)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('reports a blank or over-long type name before the progress message', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)

      await expectRejects(sales.actions.create(deal.code, action({ type: { name: '  ' }, progress: ' ' })), 422, REQUIRED)
      await expectRejects(sales.actions.create(deal.code, action({ type: { name: 'x'.repeat(51) }, progress: ' ' })), 422, TOO_LONG)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('records a history entry when only the type changes, and none when the type stays the same', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const created = await sales.actions.create(deal.code, action())
      const base = (await sales.history.list(deal.code, {})).length

      await sales.actions.update(created.id, action({ type: { name: '미팅' } }))
      expect((await sales.history.list(deal.code, {})).length).toBe(base)
      await sales.actions.update(created.id, action({ type: { name: '통화' } }))

      const history = await sales.history.list(deal.code, {})
      expect(history).toHaveLength(base + 1)
      expect(history[0]?.after.startsWith('수정: 통화 · ')).toBe(true)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('shows the renamed type on its actions while the old history text stays', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const name = unique('before')
      const created = await sales.actions.create(deal.code, action({ type: { name } }))
      const admin = await make('admin')

      await admin.actionTypes.rename(created.typeId, `${name}x`)

      expect((await admin.actions.list(deal.code, {}))[0]?.type).toBe(`${name}x`)
      expect((await admin.history.list(deal.code, {}))[0]?.after.startsWith(`등록: ${name} · `)).toBe(true)
      await admin.deals.remove(deal.code, deal.code)
      await admin.actionTypes.remove(created.typeId)
    })

    it('filters the actions by type id, and an unknown id lists nothing', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const call = await sales.actions.create(deal.code, action({ type: { name: '통화' }, progress: 'A' }))
      await sales.actions.create(deal.code, action({ type: { name: '미팅' }, progress: 'B' }))

      expect((await sales.actions.list(deal.code, { typeId: call.typeId })).map((a) => a.id)).toEqual([call.id])
      expect(await sales.actions.list(deal.code, { typeId: NO_SUCH_ID })).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })
  })
}
