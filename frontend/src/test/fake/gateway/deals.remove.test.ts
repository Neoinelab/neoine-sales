import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs } from '../testing'

describe('deals.remove (T-DELETE)', () => {
  it('user와 남의 Deal을 지우려는 sales는 403', async () => {
    const han = await mockAs('han')
    await expectApiError(han.gateway.deals.remove(dealCode(11), dealCode(11)), 403)
    const park = await mockAs('park')
    await expectApiError(park.gateway.deals.remove(dealCode(11), dealCode(11)), 403)
    expect((await park.gateway.deals.get(dealCode(11))).code).toBe(dealCode(11))
  })

  it('없는 Deal은 404, code가 일치하지 않으면 422이고 아무것도 지우지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    await expectApiError(gateway.deals.remove('20000101-ZZZZ', '20000101-ZZZZ'), 404)
    await expectApiError(gateway.deals.remove(dealCode(11), ''), 422, 'Deal code가 일치하지 않습니다.')
    await expectApiError(gateway.deals.remove(dealCode(11), dealCode(11).toLowerCase()), 422, 'Deal code가 일치하지 않습니다.')
    await expectApiError(gateway.deals.remove(dealCode(11), dealCode(12)), 422, 'Deal code가 일치하지 않습니다.')
    expect((await gateway.deals.get(dealCode(11))).code).toBe(dealCode(11))
  })

  it('본인 Deal은 삭제되고 History·Action·첨부가 연쇄 삭제된다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const before = await gateway.deals.impact(code)
    expect(before.historyCount).toBeGreaterThan(0)
    expect(before.actionCount).toBeGreaterThan(0)
    expect(before.attachmentCount).toBe(3)
    await gateway.deals.remove(code, code)
    await expectApiError(gateway.deals.get(code), 404)
    await expectApiError(gateway.history.list(code, {}), 404)
    await expectApiError(gateway.actions.list(code, {}), 404)
    await expectApiError(gateway.attachments.list(code), 404)
    expect((await gateway.deals.list({ limit: 100 })).total).toBe(23)
  })

  it('연쇄 삭제는 다른 Deal의 데이터를 건드리지 않는다', async () => {
    const { gateway } = await mockAs('root')
    const other = dealCode(10)
    const otherHistory = (await gateway.history.list(other, {})).length
    const otherActions = (await gateway.actions.list(other, {})).length
    await gateway.deals.remove(dealCode(1), dealCode(1))
    expect((await gateway.history.list(other, {})).length).toBe(otherHistory)
    expect((await gateway.actions.list(other, {})).length).toBe(otherActions)
    expect(await gateway.attachments.list(other)).toHaveLength(2)
  })

  it('admin은 모든 Deal(퇴사자 Owner 포함)을 삭제할 수 있다', async () => {
    const { gateway } = await mockAs('root')
    await gateway.deals.remove(dealCode(23), dealCode(23))
    await expectApiError(gateway.deals.get(dealCode(23)), 404)
  })

  it('삭제해도 연락처는 남는다', async () => {
    const { gateway } = await mockAs('root')
    await gateway.deals.remove(dealCode(1), dealCode(1))
    expect((await gateway.contacts.byCompany('customer', '한빛은행')).map((c) => c.name)).toContain('정민수')
  })
})
