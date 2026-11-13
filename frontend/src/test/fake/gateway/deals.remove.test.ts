import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs } from '../testing'

describe('deals.remove (T-DELETE)', () => {
  // user는 읽기 전용 문구, 남의 Deal을 지우려는 sales는 삭제 권한 문구의 403이다.
  // 테스트 코드: DD-117
  it('user와 남의 Deal을 지우려는 sales는 403', async () => {
    // given: user와 다른 영업
    const han = await mockAs('han')
    const park = await mockAs('park')
    // when·then: user가 삭제를 요청한다 → Deal 유무와 무관하게 읽기 전용 403이다(서버와 같다: user는 역할 가드가 먼저다)
    await expectApiError(han.gateway.deals.remove(dealCode(11), dealCode(11)), 403, '이 작업을 할 권한이 없습니다(읽기 전용 계정)')
    await expectApiError(han.gateway.deals.remove('20000101-ZZZZ', 'x'), 403, '이 작업을 할 권한이 없습니다(읽기 전용 계정)')
    // when·then: 다른 영업이 남의 Deal 삭제를 요청한다 → '본인 Deal 또는 admin만' 403이다
    await expectApiError(park.gateway.deals.remove(dealCode(11), dealCode(11)), 403, '본인 Deal 또는 admin만 삭제할 수 있습니다.')
    // then: Deal이 남는다
    expect((await park.gateway.deals.get(dealCode(11))).code).toBe(dealCode(11))
  })

  // 없는 Deal은 404, 확인 code가 다르면 422이고 아무것도 지우지 않는다.
  // 테스트 코드: DD-117
  it('없는 Deal은 404, code가 일치하지 않으면 422이고 아무것도 지우지 않는다', async () => {
    // given: sales 사용자
    const { gateway } = await mockAs('kim')

    // when·then: 없는 Deal과 틀린 확인 code로 삭제한다 → 404, 422이고 Deal이 남는다
    await expectApiError(gateway.deals.remove('20000101-ZZZZ', '20000101-ZZZZ'), 404)
    await expectApiError(gateway.deals.remove(dealCode(2), ''), 422, 'Deal code가 일치하지 않습니다.')
    await expectApiError(gateway.deals.remove(dealCode(2), dealCode(2).toLowerCase()), 422, 'Deal code가 일치하지 않습니다.')
    await expectApiError(gateway.deals.remove(dealCode(2), dealCode(12)), 422, 'Deal code가 일치하지 않습니다.')
    expect((await gateway.deals.get(dealCode(2))).code).toBe(dealCode(2))
  })

  // 본인 Deal을 삭제하면 이력·Action·첨부가 연쇄로 사라진다.
  // 테스트 코드: DD-117
  it('본인 Deal은 삭제되고 History·Action·첨부가 연쇄 삭제된다', async () => {
    // given: 이력·Action·첨부가 있는 Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    // when: 삭제 영향을 읽는다
    const before = await gateway.deals.impact(code)
    // then: 이력·Action·첨부가 있다
    expect(before.historyCount).toBeGreaterThan(0)
    expect(before.actionCount).toBeGreaterThan(0)
    expect(before.attachmentCount).toBe(3)
    // when: Deal을 삭제한다
    await gateway.deals.remove(code, code)
    // then: Deal·이력·Action·첨부 조회가 404이고 목록 총계가 줄어든다
    await expectApiError(gateway.deals.get(code), 404)
    await expectApiError(gateway.history.list(code, {}), 404)
    await expectApiError(gateway.actions.list(code, {}), 404)
    await expectApiError(gateway.attachments.list(code), 404)
    expect((await gateway.deals.list({ limit: 100 })).total).toBe(23)
  })

  // 연쇄 삭제는 다른 Deal의 데이터를 건드리지 않는다.
  // 테스트 코드: DD-117
  it('연쇄 삭제는 다른 Deal의 데이터를 건드리지 않는다', async () => {
    // given: admin과 다른 Deal의 이력·Action·첨부 수
    const { gateway } = await mockAs('root')
    const other = dealCode(10)
    const otherHistory = (await gateway.history.list(other, {})).length
    const otherActions = (await gateway.actions.list(other, {})).length
    // when: 한 Deal을 삭제한다
    await gateway.deals.remove(dealCode(1), dealCode(1))
    // then: 다른 Deal의 건수가 그대로다
    expect((await gateway.history.list(other, {})).length).toBe(otherHistory)
    expect((await gateway.actions.list(other, {})).length).toBe(otherActions)
    expect(await gateway.attachments.list(other)).toHaveLength(2)
  })

  // admin은 퇴사자 Owner의 Deal도 삭제한다.
  // 테스트 코드: DD-117
  it('admin은 모든 Deal(퇴사자 Owner 포함)을 삭제할 수 있다', async () => {
    // given: 퇴사자 Owner의 Deal과 admin
    const { gateway } = await mockAs('root')
    // when: 삭제한다
    await gateway.deals.remove(dealCode(23), dealCode(23))
    // then: Deal 조회가 404다
    await expectApiError(gateway.deals.get(dealCode(23)), 404)
  })

  // 삭제해도 연락처는 남는다.
  // 테스트 코드: DD-117
  it('삭제해도 연락처는 남는다', async () => {
    // given: 고객 연락처가 연결된 Deal
    const { gateway } = await mockAs('root')
    // when: 삭제한다
    await gateway.deals.remove(dealCode(1), dealCode(1))
    // then: 고객 연락처 조회에 담당자가 남아 있다
    expect((await gateway.contacts.byCompany('customer', '한빛은행')).map((c) => c.name)).toContain('정민수')
  })
})

describe('deals.remove 완료된 Deal (DD-R41)', () => {
  const COMPLETED = '완료된 Deal은 관리자만 삭제할 수 있습니다.'
  const OWNER_ONLY = '본인 Deal 또는 admin만 삭제할 수 있습니다.'

  // Fake는 Owner 영업의 완료된 Deal 삭제를 서버와 같은 문구의 403으로 막고 아무것도 지우지 않는다.
  // 테스트 코드: DD-125
  it('Owner 영업이 완료된 Deal을 지우면 완료 문구의 403이고 Deal이 남는다', async () => {
    // given: KIM이 Owner인 Won Deal(시드 11)과 그 계약 수
    const { gateway } = await mockAs('kim')
    const code = dealCode(11)
    const before = await gateway.deals.impact(code)
    expect(before.licenseContractCount).toBeGreaterThan(0)

    // when: KIM(sales)이 정확한 code로 지운다
    // then: 403 완료 문구다
    await expectApiError(gateway.deals.remove(code, code), 403, COMPLETED)

    // then: Deal·이력·Action·첨부·계약이 그대로다
    expect(await gateway.deals.get(code)).toMatchObject({ code, forecastKey: 'won' })
    expect(await gateway.deals.impact(code)).toEqual(before)
  })

  // 완료 판정이 확인 code 비교보다 먼저라 틀린 code로도 완료 문구의 403이다.
  // 테스트 코드: DD-125
  it('완료된 Deal은 확인 code가 틀려도 422가 아니라 완료 문구의 403이다', async () => {
    // given: KIM이 Owner인 Won Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(11)

    // when·then: 틀린 확인 code로 지운다 → 403 완료 문구이고 Deal이 남는다
    await expectApiError(gateway.deals.remove(code, 'wrong'), 403, COMPLETED)
    expect((await gateway.deals.get(code)).code).toBe(code)
  })

  // admin은 완료된 Deal을 지우고 이력·Action·첨부·계약이 함께 사라진다.
  // 테스트 코드: DD-125
  it('admin은 완료된 Deal을 지우고 이력·Action·첨부·계약이 함께 사라진다', async () => {
    // given: KIM이 Owner인 Won Deal(시드 11)과 admin
    const { gateway } = await mockAs('root')
    const code = dealCode(11)
    const before = await gateway.deals.impact(code)
    expect(before.historyCount).toBeGreaterThan(0)
    expect(before.licenseContractCount).toBeGreaterThan(0)

    // when: ROOT가 정확한 code로 지운다
    await gateway.deals.remove(code, code)

    // then: Deal·이력·Action·첨부 조회가 404이고 그 Deal의 계약이 없다
    await expectApiError(gateway.deals.get(code), 404)
    await expectApiError(gateway.history.list(code, {}), 404)
    await expectApiError(gateway.actions.list(code, {}), 404)
    await expectApiError(gateway.attachments.list(code), 404)
    const contracts = (await gateway.licenseContracts.list({ sort: 'licenseEnd', order: 'asc' }, 0, 200)).items.filter((c) => c.dealCode === code)
    expect(contracts).toEqual([])
  })

  // 다른 영업이 완료된 Deal을 지우면 Owner 문구가 완료 문구보다 먼저다.
  // 테스트 코드: DD-125
  it('다른 영업이 완료된 Deal을 지우면 Owner 문구의 403이 먼저다', async () => {
    // given: KIM이 Owner인 Won Deal과 다른 영업 PARK
    const { gateway } = await mockAs('park')
    const code = dealCode(11)

    // when·then: PARK가 지운다 → Owner 문구 403이고 Deal이 남는다
    await expectApiError(gateway.deals.remove(code, code), 403, OWNER_ONLY)
    expect((await gateway.deals.get(code)).code).toBe(code)
  })

  // Lost와 Won에서 되돌린 Deal은 완료가 아니라 Owner 영업이 지운다.
  // 테스트 코드: DD-125
  it('Lost Deal과 Won에서 되돌린 Deal은 Owner 영업이 지울 수 있다', async () => {
    // given: KIM이 Owner인 Lost Deal(시드 16)과, LEE가 Owner인 Won Deal(시드 12, 미발급 계약만)을 Pipeline으로 되돌린 것
    const kim = await mockAs('kim')
    const lee = await mockAs('lee')
    const lost = dealCode(16)
    const back = dealCode(12)
    await lee.gateway.deals.applyChange(back, { change: { field: 'forecastKey', value: 'pipeline' }, resolution: { statusKey: 'prospecting' } })
    expect((await lee.gateway.deals.get(back)).forecastKey).toBe('pipeline')

    // when: 각 Owner가 자기 Deal을 지운다
    await kim.gateway.deals.remove(lost, lost)
    await lee.gateway.deals.remove(back, back)

    // then: 두 Deal 모두 사라진다
    await expectApiError(kim.gateway.deals.get(lost), 404)
    await expectApiError(lee.gateway.deals.get(back), 404)
  })
})
