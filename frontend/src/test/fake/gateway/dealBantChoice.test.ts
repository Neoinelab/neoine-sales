import { describe, expect, it } from 'vitest'
import type { DealPatch } from '../../../shared/model/types'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'

const NONE = { budget: null, authority: null, need: null, timeline: null } as const

async function setup() {
  const { gateway } = await mockAs('kim')
  const labels = async () => gateway.labels.list()
  return { gateway, labels }
}

describe('Deal BANT 선택 객체 (AC-17~22, 서버 규칙)', () => {
  it('a name equal to a label of the same category reuses it, ignoring case and spaces', async () => {
    const { gateway, labels } = await setup()
    const before = (await labels()).length
    const deal = await gateway.deals.create(dealInput('u-kim', { bant: { ...NONE, budget: { name: '  단독 예산 확보 ' } } }))
    const all = await labels()
    expect(all).toHaveLength(before)
    expect(all.find((l) => l.id === deal.bant.budget)).toMatchObject({ category: 'budget', name: '단독 예산 확보', isDefault: true })
  })

  it('an unknown name creates a label in that category made by the requester, counted as used', async () => {
    const { gateway, labels } = await setup()
    const deal = await gateway.deals.create(dealInput('u-kim', { bant: { ...NONE, need: { name: ' 신규 요건 ' } } }))
    expect((await labels()).find((l) => l.id === deal.bant.need)).toMatchObject({
      category: 'need',
      name: '신규 요건',
      isDefault: false,
      usageCount: 1,
      createdBy: { id: 'u-kim' },
    })
  })

  it('the same name in another category does not reuse the other label', async () => {
    const { gateway, labels } = await setup()
    const deal = await gateway.deals.create(dealInput('u-kim', { bant: { ...NONE, authority: { name: '단독 예산 확보' } } }))
    const made = (await labels()).find((l) => l.id === deal.bant.authority)
    expect(made).toMatchObject({ category: 'authority', isDefault: false })
  })

  it('applies the label name rules in the fixed place before the procurement length', async () => {
    const { gateway } = await setup()
    await expectApiError(gateway.deals.create(dealInput('u-kim', { bant: { ...NONE, need: { name: '  ' } }, procurement: 'a'.repeat(501) })), 422, 'Label 이름을 입력하세요.')
    await expectApiError(gateway.deals.create(dealInput('u-kim', { bant: { ...NONE, need: { name: 'x'.repeat(51) } } })), 422, 'Label 이름은 50자 이내로 입력하세요.')
  })

  it('creates no label when a later validation fails, on create and on update', async () => {
    const { gateway, labels } = await setup()
    const count = (await labels()).length
    await expectApiError(gateway.deals.create(dealInput('u-kim', { bant: { ...NONE, timeline: { name: '새 일정' } }, procurement: 'a'.repeat(501) })), 422)
    const patch: DealPatch = { bant: { ...NONE, timeline: { name: '새 일정' } }, procurement: 'a'.repeat(501) }
    await expectApiError(gateway.deals.update(dealCode(2), patch), 422)
    expect(await labels()).toHaveLength(count)
  })

  it('a patch by name records one bant history entry with the new label name, none for unchanged categories', async () => {
    const { gateway } = await setup()
    const code = dealCode(2)
    const current = (await gateway.deals.get(code)).bant
    const base = (await gateway.history.list(code, { category: 'bant' })).length
    await gateway.deals.update(code, {
      bant: {
        budget: current.budget ? { id: current.budget } : null,
        authority: current.authority ? { id: current.authority } : null,
        need: current.need ? { id: current.need } : null,
        timeline: { name: '내후년 구매 검토' },
      },
    })
    const entries = await gateway.history.list(code, { category: 'bant' })
    expect(entries).toHaveLength(base + 1)
    expect(entries[0]?.after).toContain('내후년 구매 검토')
  })

  it('null clears the selection', async () => {
    const { gateway } = await setup()
    const updated = await gateway.deals.update(dealCode(1), { bant: NONE })
    expect(updated.bant).toEqual(NONE)
  })

  it('an id of another category is refused with the label message', async () => {
    const { gateway, labels } = await setup()
    const need = (await labels()).find((l) => l.category === 'need')
    await expectApiError(gateway.deals.create(dealInput('u-kim', { bant: { ...NONE, budget: { id: need?.id ?? '' } } })), 422, 'BANT Label이 올바르지 않습니다.')
  })
})
