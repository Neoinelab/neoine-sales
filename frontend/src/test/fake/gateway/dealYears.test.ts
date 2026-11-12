import { describe, expect, it } from 'vitest'
import { createMockGateway } from '../index'
import { dealInput, expectApiError, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

describe('deals.years', () => {
  it('Deal이 없으면 null을 돌려준다', async () => {
    // given: 업무 데이터가 없는 앱 기본 시드
    const mock = createMockGateway({ now: TEST_NOW, latency: false })
    await mock.signInAs(USER_ID.root)

    // when: 가장 이른 연도를 조회한다
    const result = await mock.gateway.deals.years()

    // then: earliestYear가 null이다
    expect(result).toEqual({ earliestYear: null })
  })

  it('가장 이른 Expected Close의 연도를 돌려준다', async () => {
    // given: 시드 Deal 전체에서 가장 이른 연도
    const { gateway } = await mockAs('kim')
    const all = (await gateway.deals.list({ limit: 200 })).items
    const expected = Math.min(...all.map((d) => Number(d.revenueDate.slice(0, 4))))

    // when: 가장 이른 연도를 조회한다
    const result = await gateway.deals.years()

    // then: 계산한 연도와 같다
    expect(result).toEqual({ earliestYear: expected })
  })

  it('더 오래된 Deal을 만들면 앞 연도로 옮기고 지우면 되돌아온다', async () => {
    // given: 2015년 Expected Close의 Deal을 등록했다
    const { gateway } = await mockAs('kim')
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { revenueDate: '2015-03-01' }))

    // when: 연도를 조회한다
    const withOld = await gateway.deals.years()
    // then: 2015다
    expect(withOld).toEqual({ earliestYear: 2015 })

    // when: 그 Deal을 삭제하고 다시 조회한다
    await gateway.deals.remove(created.code, created.code)
    const afterRemove = await gateway.deals.years()
    // then: 2015보다 뒤 연도다
    expect(afterRemove.earliestYear).toBeGreaterThan(2015)
  })

  it('Expected Close 수정을 따라간다', async () => {
    // given: 2027년 Expected Close의 Deal
    const { gateway } = await mockAs('kim')
    const created = await gateway.deals.create(dealInput(USER_ID.kim, { revenueDate: '2027-01-31' }))

    // when: Expected Close를 2012년으로 수정하고 연도를 조회한다
    await gateway.deals.update(created.code, { revenueDate: '2012-06-30' })
    const result = await gateway.deals.years()

    // then: 2012다
    expect(result).toEqual({ earliestYear: 2012 })
  })

  it('모든 역할이 읽을 수 있고 로그인이 필요하다', async () => {
    // when·then: 관리자·영업·조회자는 조회되고, 로그인하지 않으면 401이다
    for (const key of ['root', 'kim', 'han'] as const) {
      const { gateway } = await mockAs(key)
      await expect(gateway.deals.years()).resolves.toHaveProperty('earliestYear')
    }
    const anonymous = await mockAs(null)
    await expectApiError(anonymous.gateway.deals.years(), 401)
  })
})
