import { describe, expect, it } from 'vitest'
import type { DealPatch } from '../../../shared/model/types'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { NO_SUCH_ID, USER_ID } from '../seed/ids'

const NONE = { budget: null, authority: null, need: null, timeline: null } as const

async function setup() {
  const { gateway } = await mockAs('kim')
  const labels = async () => gateway.labels.list()
  return { gateway, labels }
}

describe('Deal BANT 선택 객체 (서버 규칙)', () => {
  it('같은 구분의 Label과 이름이 같으면 대소문자·공백을 무시하고 재사용한다', async () => {
    // given: 현재 Label 수
    const { gateway, labels } = await setup()
    const before = (await labels()).length

    // when: 기본 Label과 공백만 다른 이름으로 예산을 지정해 Deal을 등록한다
    const deal = await gateway.deals.create(dealInput(USER_ID.kim, { bant: { ...NONE, budget: { name: '  단독 예산 확보 ' } } }))
    const all = await labels()

    // then: Label 수가 늘지 않고 기존 기본 Label이 연결된다
    expect(all).toHaveLength(before)
    expect(all.find((l) => l.id === deal.bant.budget)).toMatchObject({ category: 'budget', name: '단독 예산 확보', isDefault: true })
  })

  it('없는 이름은 등록자가 만든 그 구분의 새 Label이 되고 사용 중으로 센다', async () => {
    // given: 로그인한 영업
    const { gateway, labels } = await setup()

    // when: 없는 이름을 need에 지정해 Deal을 등록한다
    const deal = await gateway.deals.create(dealInput(USER_ID.kim, { bant: { ...NONE, need: { name: ' 신규 요건 ' } } }))
    const created = (await labels()).find((l) => l.id === deal.bant.need)

    // then: 등록자가 만든 need 구분 새 Label이 사용 1건으로 생긴다
    expect(created).toMatchObject({
      category: 'need',
      name: '신규 요건',
      isDefault: false,
      usageCount: 1,
      createdBy: { id: USER_ID.kim },
    })
  })

  it('다른 구분에 있는 같은 이름은 재사용하지 않는다', async () => {
    // given: 로그인한 영업
    const { gateway, labels } = await setup()

    // when: budget 구분에 있는 이름을 authority에 지정해 Deal을 등록한다
    const deal = await gateway.deals.create(dealInput(USER_ID.kim, { bant: { ...NONE, authority: { name: '단독 예산 확보' } } }))
    const made = (await labels()).find((l) => l.id === deal.bant.authority)

    // then: authority 구분의 새 Label이 만들어진다
    expect(made).toMatchObject({ category: 'authority', isDefault: false })
  })

  it('Label 이름 규칙은 구매절차 길이보다 먼저 적용한다', async () => {
    // given: 로그인한 영업
    const { gateway } = await setup()

    // when·then: 공백 이름은 구매절차가 길어도 Label 문구로 422이고, 51자 이름도 Label 문구로 422다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { bant: { ...NONE, need: { name: '  ' } }, procurement: 'a'.repeat(501) })), 422, 'Label 이름을 입력하세요.')
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { bant: { ...NONE, need: { name: 'x'.repeat(51) } } })), 422, 'Label 이름은 50자 이내로 입력하세요.')
  })

  it('뒤 검증이 실패하면 등록에서도 수정에서도 Label을 만들지 않는다', async () => {
    // given: 현재 Label 수와 잘못된 구매절차를 가진 수정 내용
    const { gateway, labels } = await setup()
    const count = (await labels()).length
    const patch: DealPatch = { bant: { ...NONE, timeline: { name: '새 일정' } }, procurement: 'a'.repeat(501) }

    // when·then: 새 Label 이름과 501자 구매절차로 등록·수정하면 모두 422다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { bant: { ...NONE, timeline: { name: '새 일정' } }, procurement: 'a'.repeat(501) })), 422)
    await expectApiError(gateway.deals.update(dealCode(2), patch), 422)

    // then: Label 수가 그대로다
    expect(await labels()).toHaveLength(count)
  })

  it('이름으로 BANT를 수정하면 새 Label 이름이 든 bant 이력이 한 건 남고 바뀌지 않은 구분은 남지 않는다', async () => {
    // given: 기존 BANT와 현재 bant 이력 수
    const { gateway } = await setup()
    const code = dealCode(2)
    const current = (await gateway.deals.get(code)).bant
    const base = (await gateway.history.list(code, { category: 'bant' })).length

    // when: 나머지는 id로 두고 timeline만 새 이름으로 수정한다
    await gateway.deals.update(code, {
      bant: {
        budget: current.budget ? { id: current.budget } : null,
        authority: current.authority ? { id: current.authority } : null,
        need: current.need ? { id: current.need } : null,
        timeline: { name: '내후년 구매 검토' },
      },
    })
    const entries = await gateway.history.list(code, { category: 'bant' })

    // then: bant 이력이 한 건 늘고 새 Label 이름을 담는다
    expect(entries).toHaveLength(base + 1)
    expect(entries[0]?.after).toContain('내후년 구매 검토')
  })

  it('null은 선택을 지운다', async () => {
    // given: 로그인한 영업
    const { gateway } = await setup()

    // when: BANT를 모두 null로 수정한다
    const updated = await gateway.deals.update(dealCode(1), { bant: NONE })

    // then: 네 구분 모두 선택이 없다
    expect(updated.bant).toEqual(NONE)
  })

  it('다른 구분의 id는 Label 문구와 함께 거절한다', async () => {
    // given: need 구분의 Label
    const { gateway, labels } = await setup()
    const need = (await labels()).find((l) => l.category === 'need')

    // when·then: 그 id를 budget에 지정해 등록하면 Label 문구와 함께 422다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { bant: { ...NONE, budget: { id: need?.id ?? NO_SUCH_ID } } })), 422, 'BANT Label이 올바르지 않습니다.')
  })
})
