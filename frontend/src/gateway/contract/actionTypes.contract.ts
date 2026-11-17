/**
 * Action 유형 카탈로그와 Action의 유형 선택 객체 계약. mock과 실제 서버가 같은 결과를 내야 한다.
 * 이름은 호출마다 고유하게 만들고, 만든 유형은 스스로 지운다. 기본 유형 8개는 서버 시드와 같은 이름·순서다.
 */

import { describe, expect, it } from 'vitest'
import type { ActionInput, DealInput } from '../../shared/model/types'
import type { Gateway } from '../types'
import { expectRejects, unique, type MakeGateway, NO_SUCH_ID, anyVendorId } from './support'

const DEFAULTS = ['통화', '미팅', '이메일', '데모', '제안', '협상', '계약', '기타']
const DUPLICATE = '이미 있는 유형 이름입니다.'
const REQUIRED = '유형을 입력하세요.'
const TOO_LONG = '유형은 50자 이내로 입력하세요.'
const UNKNOWN = '선택한 유형이 없습니다. 목록에서 다시 선택하세요.'

async function newDeal(gateway: Gateway) {
  const me = await gateway.auth.me()
  const input: DealInput = {
    name: unique('deal'),
    ownerId: me.id,
    vendorId: await anyVendorId(gateway),
    product: 'ITDR',
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
  comment: '',
  ...over,
})

export function actionTypesContract(make: MakeGateway): void {
  describe('actionTypes 계약', () => {
    it('모든 역할이 기본 유형 8개를 순서대로 읽고 사용 0건·만든 사람 없음이다', async () => {
      for (const role of ['admin', 'sales', 'user'] as const) {
        // when: 역할마다 유형 목록에서 기본 유형을 읽는다
        const { actionTypes } = await make(role)
        const defaults = (await actionTypes.list()).filter((t) => t.isDefault)

        // then: 시드 이름·순서와 같고 만든 사람이 없다
        expect(defaults.map((t) => t.name)).toEqual(DEFAULTS)
        expect(defaults.every((t) => t.createdBy === null)).toBe(true)
      }
    })

    it('사용자 정의 유형은 기본 유형 뒤에 놓인다', async () => {
      // given: 사용자 정의 유형 하나
      const admin = await make('admin')
      const created = await admin.actionTypes.create(unique('zz'))

      // when: 목록을 읽는다
      const list = await admin.actionTypes.list()

      // then: 앞 8개는 기본 유형이고 정의 유형은 그 뒤에 있다 (끝에 정리한다)
      expect(list.slice(0, 8).map((t) => t.name)).toEqual(DEFAULTS)
      expect(list.findIndex((t) => t.id === created.id)).toBeGreaterThanOrEqual(8)
      await admin.actionTypes.remove(created.id)
    })

    it('영업은 공백을 지운 일반 유형을 만들고 조회자는 403이다', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      const name = unique('webinar')

      // when: 영업이 앞뒤 공백이 있는 이름으로 유형을 만든다
      const created = await sales.actionTypes.create(`  ${name}  `)

      // then: 공백이 지워진 일반 유형이고 만든 사람이 영업이다
      expect(created).toMatchObject({ name, isDefault: false, usageCount: 0, createdBy: { id: me.id } })
      // when·then: 조회자가 만들면 403이다 (끝에 정리한다)
      const user = await make('user')
      await expectRejects(user.actionTypes.create(unique('x')), 403)
      const admin = await make('admin')
      await admin.actionTypes.remove(created.id)
    })

    it('빈 이름과 51자 이름은 거절하고 정확히 50자는 허용한다', async () => {
      const admin = await make('admin')

      // when·then: 공백만과 51자는 각 문구와 함께 422이고 50자는 만들어진다 (끝에 정리한다)
      await expectRejects(admin.actionTypes.create('   '), 422, REQUIRED)
      await expectRejects(admin.actionTypes.create('x'.repeat(51)), 422, TOO_LONG)
      const fifty = await admin.actionTypes.create(unique('f').padEnd(50, 'x'))
      expect(Array.from(fifty.name)).toHaveLength(50)
      await admin.actionTypes.remove(fifty.id)
    })

    it('대소문자만 다른 중복 이름은 409이고 자기 이름의 대소문자 변경은 허용한다', async () => {
      const admin = await make('admin')
      // given: 유형 하나
      const name = unique('Demo')
      const created = await admin.actionTypes.create(name)

      // when·then: 대소문자만 다른 이름의 등록은 409이고, 자기 이름의 대소문자 변경은 허용되며, 기본 유형 이름으로의 변경은 409다
      await expectRejects(admin.actionTypes.create(name.toUpperCase()), 409, DUPLICATE)
      const recased = await admin.actionTypes.rename(created.id, name.toUpperCase())
      expect(recased.name).toBe(name.toUpperCase())
      await expectRejects(admin.actionTypes.rename(created.id, '미팅'), 409, DUPLICATE)
      await admin.actionTypes.remove(created.id)
    })

    it('이름 변경과 삭제는 admin만 하고 없는 id는 404다', async () => {
      const admin = await make('admin')
      // given: admin이 만든 유형 하나
      const created = await admin.actionTypes.create(unique('own'))
      const sales = await make('sales')

      // when·then: 영업의 이름 변경·삭제는 403이고 admin이 없는 id를 바꾸거나 지우면 404다 (끝에 정리한다)
      await expectRejects(sales.actionTypes.rename(created.id, unique('new')), 403)
      await expectRejects(sales.actionTypes.remove(created.id), 403)
      const again = await make('admin')
      await expectRejects(again.actionTypes.rename(NO_SUCH_ID, unique('new')), 404)
      await expectRejects(again.actionTypes.remove(NO_SUCH_ID), 404)
      await again.actionTypes.remove(created.id)
    })

    it('유형을 쓰는 Action 수를 세고 그 건수와 함께 삭제를 거절한다', async () => {
      // given: 한 유형을 쓰는 Action 두 건
      const sales = await make('sales')
      const deal = await newDeal(sales)
      const name = unique('used')
      await sales.actions.create(deal.code, action({ type: { name } }))
      await sales.actions.create(deal.code, action({ type: { name } }))
      const admin = await make('admin')

      // when: 유형 목록에서 방금 쓴 유형을 찾는다
      const used = (await admin.actionTypes.list()).find((t) => t.name === name)
      // then: 사용 건수가 2이다
      expect(used?.usageCount).toBe(2)

      // when·then: 삭제하면 건수 문구와 함께 409이며 유형은 남는다 (끝에 정리한다)
      await expectRejects(admin.actionTypes.remove(used?.id ?? NO_SUCH_ID), 409, '사용 중인 유형은 삭제할 수 없습니다. (Action 2건)')
      expect((await admin.actionTypes.list()).some((t) => t.id === used?.id)).toBe(true)
      await admin.deals.remove(deal.code, deal.code)
      await admin.actionTypes.remove(used?.id ?? NO_SUCH_ID)
    })
  })

  describe('Action 유형 선택 객체 계약', () => {
    it('id로 고른 유형을 쓰고 응답에 그 id와 현재 이름을 담는다', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Deal과 기본 유형 미팅
      const meeting = (await sales.actionTypes.list()).find((t) => t.name === '미팅')

      // when: 유형 id로 Action을 등록한다
      const created = await sales.actions.create(deal.code, action({ type: { id: meeting?.id ?? NO_SUCH_ID } }))

      // then: 유형 이름과 id가 응답에 담긴다 (끝에 정리한다)
      expect(created).toMatchObject({ type: '미팅', typeId: meeting?.id })
      await sales.deals.remove(deal.code, deal.code)
    })

    it('없는 유형 id는 다시 고르라는 문구와 함께 422다', async () => {
      const sales = await make('sales')
      // given: Deal 하나
      const deal = await newDeal(sales)

      // when·then: 없는 유형 id로 등록하면 422와 다시 선택 문구다 (끝에 정리한다)
      await expectRejects(sales.actions.create(deal.code, action({ type: { id: NO_SUCH_ID } })), 422, UNKNOWN)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('대소문자·공백만 다른 이름은 유형을 새로 만들지 않고 재사용한다', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Deal과 현재 유형 수
      const before = (await sales.actionTypes.list()).length

      // when: 기본 유형과 공백만 다른 이름으로 Action을 등록한다
      const created = await sales.actions.create(deal.code, action({ type: { name: ' 데모 ' } }))

      // then: 기존 유형 이름이 쓰이고 유형 수가 늘지 않는다 (끝에 정리한다)
      expect(created.type).toBe('데모')
      expect((await sales.actionTypes.list()).length).toBe(before)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('없는 이름은 같은 요청에서 등록자가 만든 새 유형이 된다', async () => {
      const sales = await make('sales')
      const me = await sales.auth.me()
      const deal = await newDeal(sales)
      // given: Deal과 존재하지 않는 유형 이름
      const name = unique('seminar')

      // when: 그 이름으로 Action을 등록한다
      const created = await sales.actions.create(deal.code, action({ type: { name: `  ${name} ` } }))

      // then: 새 유형이 사용 1건, 등록자가 만든 사람으로 생긴다 (끝에 정리한다)
      expect(created.type).toBe(name)
      const added = (await sales.actionTypes.list()).find((t) => t.id === created.typeId)
      expect(added).toMatchObject({ name, isDefault: false, usageCount: 1, createdBy: { id: me.id } })
      await sales.deals.remove(deal.code, deal.code)
      await (await make('admin')).actionTypes.remove(created.typeId)
    })

    it('등록이 실패하면 유형을 만들지 않는다', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Deal과 아직 없는 유형 이름
      const name = unique('ghost')

      // when: 새 유형 이름과 비어 있는 진행사항·Next Action으로 등록을 시도한다
      await expectRejects(sales.actions.create(deal.code, action({ type: { name }, progress: ' ', nextAction: '', dueDate: '' })), 422, '진행사항 또는 Next Action을 입력하세요.')

      // then: 등록이 422로 거절되고 새 유형은 만들어지지 않는다 (끝에 정리한다)
      expect((await sales.actionTypes.list()).some((t) => t.name === name)).toBe(false)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('유형 이름이 비었거나 길면 진행사항 문구보다 먼저 알린다', async () => {
      const sales = await make('sales')
      // given: Deal 하나
      const deal = await newDeal(sales)

      // when·then: 빈 유형 이름·51자 이름은 진행사항이 비어 있어도 유형 문구로 422다 (끝에 정리한다)
      await expectRejects(sales.actions.create(deal.code, action({ type: { name: '  ' }, progress: ' ' })), 422, REQUIRED)
      await expectRejects(sales.actions.create(deal.code, action({ type: { name: 'x'.repeat(51) }, progress: ' ' })), 422, TOO_LONG)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('유형만 바뀌면 이력이 한 건 남고 같으면 남지 않는다', async () => {
      const sales = await make('sales')
      const deal = await newDeal(sales)
      // given: Action 하나와 현재 이력 수
      const created = await sales.actions.create(deal.code, action())
      const base = (await sales.history.list(deal.code, {})).length

      // when: 같은 유형으로 수정한다
      await sales.actions.update(created.id, action({ type: { name: '미팅' } }))
      // then: 이력 수가 그대로다
      expect((await sales.history.list(deal.code, {})).length).toBe(base)
      // when: 다른 유형으로 수정한다
      await sales.actions.update(created.id, action({ type: { name: '통화' } }))

      // then: 수정 이력이 한 건 늘고 새 유형 이름으로 시작한다 (끝에 정리한다)
      const history = await sales.history.list(deal.code, {})
      expect(history).toHaveLength(base + 1)
      expect(history[0]?.after.startsWith('수정: 통화 · ')).toBe(true)
      await sales.deals.remove(deal.code, deal.code)
    })

    it('유형 이름을 바꾸면 Action에는 새 이름이 보이고 옛 이력 문구는 그대로다', async () => {
      const sales = await make('sales')
      // given: 유형을 쓰는 Action과 등록 이력
      const deal = await newDeal(sales)
      const name = unique('before')
      const created = await sales.actions.create(deal.code, action({ type: { name } }))
      const admin = await make('admin')

      // when: admin이 유형 이름을 바꾼다
      await admin.actionTypes.rename(created.typeId, `${name}x`)

      // then: Action 목록은 새 이름이고 이력의 등록 문구는 옛 이름 그대로다 (끝에 정리한다)
      expect((await admin.actions.list(deal.code, {}))[0]?.type).toBe(`${name}x`)
      expect((await admin.history.list(deal.code, {}))[0]?.after.startsWith(`등록: ${name} · `)).toBe(true)
      await admin.deals.remove(deal.code, deal.code)
      await admin.actionTypes.remove(created.typeId)
    })

    it('유형 id로 Action을 거르고 없는 id는 빈 목록이다', async () => {
      const sales = await make('sales')
      // given: 통화·미팅 유형의 Action 두 건
      const deal = await newDeal(sales)
      const call = await sales.actions.create(deal.code, action({ type: { name: '통화' }, progress: 'A' }))
      await sales.actions.create(deal.code, action({ type: { name: '미팅' }, progress: 'B' }))

      // when: 통화 유형 id와 없는 id로 각각 거른다
      const calls = (await sales.actions.list(deal.code, { typeId: call.typeId })).map((a) => a.id)
      const none = await sales.actions.list(deal.code, { typeId: NO_SUCH_ID })

      // then: 통화 Action만, 없는 id면 빈 목록이다 (끝에 정리한다)
      expect(calls).toEqual([call.id])
      expect(none).toEqual([])
      await sales.deals.remove(deal.code, deal.code)
    })
  })
}
