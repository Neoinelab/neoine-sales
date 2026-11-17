import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'
import { USER_ID } from '../seed/ids'

const REVENUE_MSG = 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'
const CHOICE_MSG = '함께 바꿀 값을 선택하세요.'

describe('deals.applyChange', () => {
  // user의 단일 변경은 403이다.
  // 테스트 코드: DD-117
  it('T-GW user는 403', async () => {
    // given: user 역할 사용자
    const { gateway } = await mockAs('han')

    // when·then: Fake로 변경을 요청한다 → 403 오류다
    await expectApiError(
      gateway.deals.applyChange(dealCode(2), { change: { field: 'forecastKey', value: 'commit' } }),
      403,
    )
  })

  // 독립 변경은 바로 저장되고 이력 한 건이 남는다.
  // 테스트 코드: DD-117
  it('독립 변경은 바로 저장되고 History 1건이 남는다', async () => {
    // given: Most Likely Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length
    // when: Forecast를 Commit으로 바꾼다
    const result = await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'commit' } })
    // then: 함께 바뀐 값·알림 없이 수정 시각이 서버 시각이고 이력 한 건(변경자 포함)이 늘어난다
    expect(result.deal.forecastKey).toBe('commit')
    expect(result.coChanged).toEqual([])
    expect(result.notice).toBeNull()
    expect(result.deal.updatedAt).toBe(TEST_NOW)
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'forecast', before: 'Most Likely', after: 'Commit', by: { id: USER_ID.kim } })
  })

  // 같은 값으로 바꾸면 이력이 늘지 않는다.
  // 테스트 코드: DD-117
  it('같은 값으로 바꾸면 변화도 History도 없다', async () => {
    // given: Most Likely Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length
    // when: 같은 Forecast로 바꾼다
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'most_likely' } })
    // then: 이력 수가 그대로다
    expect((await gateway.history.list(code, {})).length).toBe(base)
  })

  // 매출 없이 계약완료로 바꾸면 422이고 값이 그대로다.
  // 테스트 코드: DD-117
  it('T-SYNC Status→계약완료: 매출 입력 없으면 422이고 아무것도 바뀌지 않는다', async () => {
    // given: 가격협상·Commit Deal
    const { gateway } = await mockAs('kim')
    // when: 매출 답 없이, 금액 0으로 계약완료로 바꾼다
    const code = dealCode(1)
    // then: 매출 문구의 422이고 Status·Forecast가 그대로다
    await expectApiError(gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'contract_completed' } }), 422, REVENUE_MSG)
    await expectApiError(
      gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'contract_completed' }, resolution: { revenueAmount: 0, revenueDate: '2026-10-15' } }),
      422,
      REVENUE_MSG,
    )
    const deal = await gateway.deals.get(code)
    expect([deal.statusKey, deal.forecastKey]).toEqual(['price_negotiation', 'commit'])
  })

  // 계약완료로 바꾸면 Forecast도 Won, 매출 저장, 알림, 이력 4종이 남는다.
  // 테스트 코드: DD-117
  it('T-SYNC Status→계약완료: Forecast=Won, 실제 매출 저장, 알림, History 4종', async () => {
    // given: 가격협상·Commit Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const base = (await gateway.history.list(code, {})).length
    // when: 매출 답과 함께 계약완료로 바꾼다
    const result = await gateway.deals.applyChange(code, {
      change: { field: 'statusKey', value: 'contract_completed' },
      resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-14' },
    })
    // then: 계약완료·Won·매출이 저장되고 함께 바뀐 Forecast·알림, status·forecast·amount·expectedClose 이력이 남는다
    expect(result.deal).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 1_800_000_000, revenueDate: '2026-10-14', risk: null })
    expect(result.coChanged).toEqual([{ field: 'forecastKey', from: 'commit', to: 'won' }])
    expect(result.notice).toBe("Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다.")
    const added = (await gateway.history.list(code, {})).slice(0, -base)
    expect(added.map((h) => h.category).sort()).toEqual(['amount', 'expectedClose', 'forecast', 'status'])
    expect(added.find((h) => h.category === 'forecast')?.after).toContain('함께 변경')
  })

  // Won으로 바꾸면 Status도 계약완료가 된다.
  // 테스트 코드: DD-117
  it('T-SYNC Forecast→Won도 Status=계약완료를 함께 바꾼다', async () => {
    // given: 기술평가 Deal
    const { gateway } = await mockAs('kim')
    // when: 매출 답과 함께 Won으로 바꾼다
    const result = await gateway.deals.applyChange(dealCode(2), {
      change: { field: 'forecastKey', value: 'won' },
      resolution: { revenueAmount: 400_000_000, revenueDate: '2026-10-15' },
    })
    // then: 계약완료·Won이고 함께 바뀐 Status가 있다
    expect(result.deal).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
    expect(result.coChanged).toEqual([{ field: 'statusKey', from: 'technical_evaluation', to: 'contract_completed' }])
  })

  // Won에서 벗어나면 Status 선택이 필수이고 계약완료는 거부되며 금액은 그대로다.
  // 테스트 코드: DD-117
  it('T-SYNC Won에서 다른 Forecast로: Status 선택이 필수이고 계약완료는 고를 수 없다', async () => {
    // given: 계약완료·Won Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(12)
    // when: 답 없이, 계약완료를 골라, 가격협상을 골라 Forecast를 Commit으로 바꾼다
    const change = { field: 'forecastKey', value: 'commit' } as const
    // then: 앞의 둘은 선택 필요 422, 마지막은 적용·알림이고 금액이 유지된다
    await expectApiError(gateway.deals.applyChange(code, { change }), 422, CHOICE_MSG)
    await expectApiError(gateway.deals.applyChange(code, { change, resolution: { statusKey: 'contract_completed' } }), 422, CHOICE_MSG)
    expect((await gateway.deals.get(code)).forecastKey).toBe('won')
    const result = await gateway.deals.applyChange(code, { change, resolution: { statusKey: 'price_negotiation' } })
    expect(result.deal).toMatchObject({ statusKey: 'price_negotiation', forecastKey: 'commit' })
    expect(result.notice).toBe("Status가 '가격협상'으로 함께 변경되었습니다.")
    // 되돌려도 매출금액·매출일은 그대로
    expect(result.deal.revenueAmount).toBe(520_000_000)
  })

  // Lost에서 되돌리면 Status를 묻되 현재 값을 그대로 고를 수 있다.
  // 테스트 코드: DD-117
  it('T-SYNC Lost에서 되돌리면 Status를 묻되 현재 값을 그대로 둘 수 있다', async () => {
    // given: Lost Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(16)
    // when: 답 없이, 현재 Status를 골라 Forecast를 Best로 바꾼다
    const change = { field: 'forecastKey', value: 'best' } as const
    // then: 처음은 선택 필요 422, 다음은 적용되고 함께 바뀐 값이 없다
    await expectApiError(gateway.deals.applyChange(code, { change }), 422, CHOICE_MSG)
    const result = await gateway.deals.applyChange(code, { change, resolution: { statusKey: 'price_negotiation' } })
    expect(result.deal.forecastKey).toBe('best')
    expect(result.coChanged).toEqual([])
  })

  // 계약완료에서 이전 단계로 가면 Forecast 선택이 필수이고 Won은 거부된다.
  // 테스트 코드: DD-117
  it('T-SYNC 계약완료에서 이전 단계로: Forecast 선택이 필수이고 Won은 거부한다', async () => {
    // given: 계약완료·Won Deal
    const { gateway } = await mockAs('kim')
    const code = dealCode(12)
    // when: 답 없이, Won을, Best를 골라 Status를 바꾼다
    const change = { field: 'statusKey', value: 'technical_evaluation' } as const
    // then: 앞의 둘은 선택 필요 422, 마지막은 적용되고 함께 바뀐 Forecast가 있다
    await expectApiError(gateway.deals.applyChange(code, { change }), 422, CHOICE_MSG)
    await expectApiError(gateway.deals.applyChange(code, { change, resolution: { forecastKey: 'won' } }), 422, CHOICE_MSG)
    const result = await gateway.deals.applyChange(code, { change, resolution: { forecastKey: 'best' } })
    expect(result.deal).toMatchObject({ statusKey: 'technical_evaluation', forecastKey: 'best' })
    expect(result.coChanged).toEqual([{ field: 'forecastKey', from: 'won', to: 'best' }])
  })

  // Lost로 바꾸면 Status는 그대로다.
  // 테스트 코드: DD-117
  it('Forecast→Lost는 Status를 그대로 둔다', async () => {
    // given: 기술평가 Deal
    const { gateway } = await mockAs('kim')
    // when: Forecast를 Lost로 바꾼다
    const result = await gateway.deals.applyChange(dealCode(2), { change: { field: 'forecastKey', value: 'lost' } })
    // then: Status 그대로 Lost가 된다
    expect(result.deal).toMatchObject({ statusKey: 'technical_evaluation', forecastKey: 'lost', risk: null })
  })

  // 없는 코드 key는 422다.
  // 테스트 코드: DD-117
  it('알 수 없는 코드 key는 422', async () => {
    // given: Deal 하나
    const { gateway } = await mockAs('kim')

    // when·then: 없는 Status key로 바꾼다 → 422 오류다
    await expectApiError(gateway.deals.applyChange(dealCode(2), { change: { field: 'statusKey', value: 'nope' } }), 422)
  })

  // 금액·Expected Close 변경은 서버와 같은 검증을 하고 이력이 남는다.
  // 테스트 코드: DD-117
  it('금액·Expected Close 변경: 검증 문구와 History', async () => {
    // given: Deal 하나
    const { gateway } = await mockAs('kim')
    const code = dealCode(4)
    // when: 금액 0, 1.5, 날짜 ''와 정상 값으로 바꾼다
    const lastUpdatedBefore = (await gateway.deals.get(code)).lastUpdatedOn
    // then: 0은 값 오류, 1.5와 ''은 요청 형식 오류이며 정상 값은 저장되고 이력이 남는다
    await expectApiError(gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 0 } }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
    // 서버와 같다: 정수가 아닌 금액·날짜 형식이 아닌 값은 요청 형식 오류(request-validation)다
    await expectApiError(gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 1.5 } }), 422, '요청 형식이 올바르지 않습니다')
    await expectApiError(gateway.deals.applyChange(code, { change: { field: 'revenueDate', value: '' } }), 422, '요청 형식이 올바르지 않습니다')
    const a = await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 350_000_000 } })
    expect(a.deal.revenueAmount).toBe(350_000_000)
    const b = await gateway.deals.applyChange(code, { change: { field: 'revenueDate', value: '2026-12-30' } })
    expect(b.deal.revenueDate).toBe('2026-12-30')
    const history = await gateway.history.list(code, {})
    expect(history[0]).toMatchObject({ category: 'expectedClose', after: '2026-12-30' })
    expect(history[1]).toMatchObject({ category: 'amount', target: '금액(단위:원)', before: '310,000,000', after: '350,000,000' })
    // E4: Inline 수정은 최종 업데이트를 바꾸지 않으므로 미업데이트가 풀리지 않는다
    expect(b.deal.lastUpdatedOn).toBe(lastUpdatedBefore)
    expect(b.deal.risk).toBe('stale')
  })
})

describe('E4 최종 업데이트는 Action 기준', () => {
  // Deal을 수정해도 최종 업데이트일과 미업데이트 경고는 바뀌지 않는다.
  it('Deal 수정(PATCH)도 lastUpdatedOn과 미업데이트를 바꾸지 않는다', async () => {
    // given: 미업데이트 경고가 있는 Deal(4번)
    const { gateway } = await mockAs('kim')
    const code = dealCode(4) // 미업데이트
    const before = await gateway.deals.get(code)
    expect(before.risk).toBe('stale')

    // when: Deal 이름 외 필드(구매절차)를 수정한다
    const after = await gateway.deals.update(code, { procurement: '수정' })

    // then: lastUpdatedOn이 그대로이고 risk는 여전히 stale이다
    expect(after.lastUpdatedOn).toBe(before.lastUpdatedOn)
    expect(after.risk).toBe('stale')
  })

  // 진행사항만 있는 Action을 등록하면 그 수행일이 최종 업데이트일이 된다.
  it('진행사항만 있는 Action의 수행일이 lastUpdatedOn이다', async () => {
    // given: Deal 2번
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    // when: 진행사항만 있는 Action을 등록한다
    const created = await gateway.actions.create(code, {
      type: { name: '미팅' },
      progress: '진행만',
      nextAction: '',
      dueDate: '',
      comment: '',
    })
    const result = (await gateway.deals.get(code)).lastUpdatedOn
    // then: Deal의 lastUpdatedOn이 Action의 수행일이다
    expect(result).toBe(created.actedOn)
  })
})
