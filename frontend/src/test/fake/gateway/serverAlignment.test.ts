/** mock을 서버 규칙(domain/deal/values.py, ports/deal_repository.py)에 맞춘 회귀. */

import { describe, expect, it } from 'vitest'
import { dealCode, dealInput, expectApiError, mockAs } from '../testing'
import { USER_ID } from '../seed/ids'

describe('Deal Name length', () => {
  it('등록할 때 200자 이름을 받아들인다', async () => {
    // given: 영업으로 로그인한 mock(등록할 때 200자 이름을 받아들인다)
    const { gateway } = await mockAs('kim')

    // when: 200자 이름으로 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { name: 'a'.repeat(200) }))

    // then: 200자 이름으로 등록된다
    expect(created.name).toHaveLength(200)
  })

  it('등록할 때 201자 이름은 서버 문구와 함께 거절한다', async () => {
    // given: 영업으로 로그인한 mock(등록할 때 201자 이름은 서버 문구와 함께 거절한다)
    const { gateway } = await mockAs('kim')

    // when·then: 201자 이름으로 등록하면 서버 문구와 함께 422다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { name: 'a'.repeat(201) })), 422, 'Deal Name은 200자 이내로 입력하세요.')
  })

  it('수정할 때 201자 이름은 거절하고 이름을 유지한다', async () => {
    // given: 현재 이름
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const before = (await gateway.deals.get(code)).name

    // when·then: 201자 이름으로 수정하면 422다
    await expectApiError(gateway.deals.update(code, { name: 'a'.repeat(201) }), 422, 'Deal Name은 200자 이내로 입력하세요.')

    // then: 이름이 그대로다
    expect((await gateway.deals.get(code)).name).toBe(before)
  })
})

describe('procurement length', () => {
  it('500자 구매절차를 받아들인다', async () => {
    // given: 영업으로 로그인한 mock(500자 구매절차를 받아들인다)
    const { gateway } = await mockAs('kim')

    // when: 500자 구매절차로 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { procurement: '가'.repeat(500) }))

    // then: 500자로 등록된다
    expect(created.procurement).toHaveLength(500)
  })

  it('501자 구매절차는 등록과 수정 모두 거절한다', async () => {
    // given: 영업으로 로그인한 mock(501자 구매절차는 등록과 수정 모두 거절한다)
    const { gateway } = await mockAs('kim')

    // when·then: 501자 구매절차로 등록·수정하면 모두 구매절차 문구와 함께 422다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { procurement: '가'.repeat(501) })), 422, '구매절차는 500자 이내로 입력하세요.')
    await expectApiError(gateway.deals.update(dealCode(2), { procurement: '가'.repeat(501) }), 422, '구매절차는 500자 이내로 입력하세요.')
  })
})

describe('Users count upper bound', () => {
  it('서버가 저장하는 가장 큰 정수(2147483647)를 받아들인다', async () => {
    // given: 영업으로 로그인한 mock(서버가 저장하는 가장 큰 정수(2147483647)를 받아들인다)
    const { gateway } = await mockAs('kim')

    // when: Users count 2147483647로 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { users: 2_147_483_647 }))

    // then: 그 값으로 등록된다
    expect(created.users).toBe(2_147_483_647)
  })

  it('하나 더 큰 값은 등록과 수정 모두 Users count 문구로 거절한다', async () => {
    // given: 영업으로 로그인한 mock(하나 더 큰 값은 등록과 수정 모두 Users count 문구로 거절한다)
    const { gateway } = await mockAs('kim')

    // when·then: 2147483648로 등록·수정하면 모두 Users count 문구와 함께 422다
    await expectApiError(gateway.deals.create(dealInput(USER_ID.kim, { users: 2_147_483_648 })), 422, 'Users count는 0 이상의 정수로 입력하세요.')
    await expectApiError(gateway.deals.update(dealCode(2), { users: 2_147_483_648 }), 422, 'Users count는 0 이상의 정수로 입력하세요.')
  })

  it('등록할 때 Users count 0을 받아들인다', async () => {
    // given: 영업으로 로그인한 mock(등록할 때 Users count 0을 받아들인다)
    const { gateway } = await mockAs('kim')

    // when: Users count 0으로 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { users: 0 }))

    // then: 0으로 등록된다
    expect(created.users).toBe(0)
  })
})

describe('deals.list quarter', () => {
  it('연도 없이 분기만 주면 올해로 읽는다', async () => {
    // given: Fake 시계 2026-10-15의 영업 mock
    const { gateway } = await mockAs('kim')

    // when: 분기만 준 조회와 올해를 명시한 조회를 한다
    const quarterOnly = await gateway.deals.list({ quarters: [4], limit: 100 })
    const explicit = await gateway.deals.list({ year: 2026, quarters: [4], limit: 100 })

    // then: 결과가 있고 두 조회의 Deal이 같다
    expect(quarterOnly.total).toBeGreaterThan(0)
    expect(quarterOnly.items.map((d) => d.code)).toEqual(explicit.items.map((d) => d.code))
  })

  it('연도만 줘도, 연도와 분기를 같이 줘도 받아들인다', async () => {
    // given: 영업으로 로그인한 mock(연도만 줘도, 연도와 분기를 같이 줘도 받아들인다)
    const { gateway } = await mockAs('kim')

    // when: 연도만, 연도와 분기로 각각 조회한다
    const byYear = await gateway.deals.list({ year: 2026 })
    const byQuarter = await gateway.deals.list({ year: 2026, quarters: [4] })

    // then: 모두 total이 있는 결과가 돌아온다
    expect(byYear).toHaveProperty('total')
    expect(byQuarter).toHaveProperty('total')
  })
})

describe('trim before the length check', () => {
  it('앞뒤 공백이 있는 500자 구매절차를 받아들이고 공백을 지워 저장한다', async () => {
    // given: 영업으로 로그인한 mock(앞뒤 공백이 있는 500자 구매절차를 받아들이고 공백을 지워 저장한다)
    const { gateway } = await mockAs('kim')

    // when: 앞뒤 공백이 붙은 500자 구매절차로 등록한다
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { procurement: `  ${'가'.repeat(500)}  ` }))

    // then: 공백이 지워진 500자로 저장된다
    expect(created.procurement).toBe('가'.repeat(500))
  })

  it('공백을 지워도 501자인 구매절차는 거절한다', async () => {
    // given: 영업으로 로그인한 mock(공백을 지워도 501자인 구매절차는 거절한다)
    const { gateway } = await mockAs('kim')

    // when·then: 앞뒤 공백이 붙은 501자 구매절차로 등록하면 422다
    await expectApiError(
      gateway.deals.create(dealInput(USER_ID.kim, { procurement: ` ${'가'.repeat(501)} ` })),
      422,
      '구매절차는 500자 이내로 입력하세요.',
    )
  })

  it('수정할 때도 한도 안에서 구매절차 공백을 지운다', async () => {
    // given: 영업으로 로그인한 mock(수정할 때도 한도 안에서 구매절차 공백을 지운다)
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)

    // when: 앞뒤 공백이 붙은 500자 구매절차로 수정한다
    const updated = await gateway.deals.update(code, { procurement: `  ${'가'.repeat(500)}  ` })

    // then: 공백이 지워진 500자로 저장된다
    expect(updated.procurement).toBe('가'.repeat(500))
  })
})
