import { describe, expect, it } from 'vitest'
import { dealCode, expectApiError, mockAs, TEST_NOW } from '../testing'

const REVENUE_MSG = 'Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.'
const CHOICE_MSG = '함께 바꿀 값을 선택하세요.'

describe('deals.applyChange', () => {
  it('T-GW user는 403', async () => {
    const { gateway } = await mockAs('han')
    await expectApiError(
      gateway.deals.applyChange(dealCode(2), { change: { field: 'forecastKey', value: 'commit' } }),
      403,
    )
  })

  it('독립 변경은 바로 저장되고 History 1건이 남는다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length
    const result = await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'commit' } })
    expect(result.deal.forecastKey).toBe('commit')
    expect(result.coChanged).toEqual([])
    expect(result.notice).toBeNull()
    expect(result.deal.updatedAt).toBe(TEST_NOW)
    const history = await gateway.history.list(code, {})
    expect(history).toHaveLength(base + 1)
    expect(history[0]).toMatchObject({ category: 'forecast', before: 'Most Likely', after: 'Commit', by: { id: 'u-kim' } })
  })

  it('같은 값으로 바꾸면 변화도 History도 없다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(2)
    const base = (await gateway.history.list(code, {})).length
    await gateway.deals.applyChange(code, { change: { field: 'forecastKey', value: 'most_likely' } })
    expect((await gateway.history.list(code, {})).length).toBe(base)
  })

  it('T-SYNC Status→계약완료: 매출 입력 없으면 422이고 아무것도 바뀌지 않는다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    await expectApiError(gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'contract_completed' } }), 422, REVENUE_MSG)
    await expectApiError(
      gateway.deals.applyChange(code, { change: { field: 'statusKey', value: 'contract_completed' }, resolution: { revenueAmount: 0, revenueDate: '2026-10-15' } }),
      422,
      REVENUE_MSG,
    )
    const deal = await gateway.deals.get(code)
    expect([deal.statusKey, deal.forecastKey]).toEqual(['price_negotiation', 'commit'])
  })

  it('T-SYNC Status→계약완료: Forecast=Won, 실제 매출 저장, 알림, History 4종', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(1)
    const base = (await gateway.history.list(code, {})).length
    const result = await gateway.deals.applyChange(code, {
      change: { field: 'statusKey', value: 'contract_completed' },
      resolution: { revenueAmount: 1_800_000_000, revenueDate: '2026-10-14' },
    })
    expect(result.deal).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won', revenueAmount: 1_800_000_000, revenueDate: '2026-10-14', risk: null })
    expect(result.coChanged).toEqual([{ field: 'forecastKey', from: 'commit', to: 'won' }])
    expect(result.notice).toBe("Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다.")
    const added = (await gateway.history.list(code, {})).slice(0, -base)
    expect(added.map((h) => h.category).sort()).toEqual(['amount', 'expectedClose', 'forecast', 'status'])
    expect(added.find((h) => h.category === 'forecast')?.after).toContain('함께 변경')
  })

  it('T-SYNC Forecast→Won도 Status=계약완료를 함께 바꾼다', async () => {
    const { gateway } = await mockAs('kim')
    const result = await gateway.deals.applyChange(dealCode(2), {
      change: { field: 'forecastKey', value: 'won' },
      resolution: { revenueAmount: 400_000_000, revenueDate: '2026-10-15' },
    })
    expect(result.deal).toMatchObject({ statusKey: 'contract_completed', forecastKey: 'won' })
    expect(result.coChanged).toEqual([{ field: 'statusKey', from: 'technical_evaluation', to: 'contract_completed' }])
  })

  it('T-SYNC Won에서 다른 Forecast로: Status 선택이 필수이고 계약완료는 고를 수 없다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(11)
    const change = { field: 'forecastKey', value: 'commit' } as const
    await expectApiError(gateway.deals.applyChange(code, { change }), 422, CHOICE_MSG)
    await expectApiError(gateway.deals.applyChange(code, { change, resolution: { statusKey: 'contract_completed' } }), 422, CHOICE_MSG)
    expect((await gateway.deals.get(code)).forecastKey).toBe('won')
    const result = await gateway.deals.applyChange(code, { change, resolution: { statusKey: 'price_negotiation' } })
    expect(result.deal).toMatchObject({ statusKey: 'price_negotiation', forecastKey: 'commit' })
    expect(result.notice).toBe("Status가 '가격협상'으로 함께 변경되었습니다.")
    // 되돌려도 매출금액·매출일은 그대로
    expect(result.deal.revenueAmount).toBe(150_000_000)
  })

  it('T-SYNC Lost에서 되돌리면 Status를 묻되 현재 값을 그대로 둘 수 있다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(16)
    const change = { field: 'forecastKey', value: 'best' } as const
    await expectApiError(gateway.deals.applyChange(code, { change }), 422, CHOICE_MSG)
    const result = await gateway.deals.applyChange(code, { change, resolution: { statusKey: 'price_negotiation' } })
    expect(result.deal.forecastKey).toBe('best')
    expect(result.coChanged).toEqual([])
  })

  it('T-SYNC 계약완료에서 이전 단계로: Forecast 선택이 필수이고 Won은 거부한다', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(11)
    const change = { field: 'statusKey', value: 'technical_evaluation' } as const
    await expectApiError(gateway.deals.applyChange(code, { change }), 422, CHOICE_MSG)
    await expectApiError(gateway.deals.applyChange(code, { change, resolution: { forecastKey: 'won' } }), 422, CHOICE_MSG)
    const result = await gateway.deals.applyChange(code, { change, resolution: { forecastKey: 'best' } })
    expect(result.deal).toMatchObject({ statusKey: 'technical_evaluation', forecastKey: 'best' })
    expect(result.coChanged).toEqual([{ field: 'forecastKey', from: 'won', to: 'best' }])
  })

  it('Forecast→Lost는 Status를 그대로 둔다', async () => {
    const { gateway } = await mockAs('kim')
    const result = await gateway.deals.applyChange(dealCode(2), { change: { field: 'forecastKey', value: 'lost' } })
    expect(result.deal).toMatchObject({ statusKey: 'technical_evaluation', forecastKey: 'lost', risk: null })
  })

  it('알 수 없는 코드 key는 422', async () => {
    const { gateway } = await mockAs('kim')
    await expectApiError(gateway.deals.applyChange(dealCode(2), { change: { field: 'statusKey', value: 'nope' } }), 422)
  })

  it('금액·Expected Close 변경: 검증 문구와 History', async () => {
    const { gateway } = await mockAs('kim')
    const code = dealCode(4)
    await expectApiError(gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 0 } }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
    await expectApiError(gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 1.5 } }), 422, '매출금액은 1원 이상의 정수로 입력하세요.')
    await expectApiError(gateway.deals.applyChange(code, { change: { field: 'revenueDate', value: '' } }), 422, 'Expected Close를 입력하세요.')
    const a = await gateway.deals.applyChange(code, { change: { field: 'revenueAmount', value: 350_000_000 } })
    expect(a.deal.revenueAmount).toBe(350_000_000)
    const b = await gateway.deals.applyChange(code, { change: { field: 'revenueDate', value: '2026-12-30' } })
    expect(b.deal.revenueDate).toBe('2026-12-30')
    const history = await gateway.history.list(code, {})
    expect(history[0]).toMatchObject({ category: 'expectedClose', after: '2026-12-30' })
    expect(history[1]).toMatchObject({ category: 'amount', before: '310,000,000원', after: '350,000,000원' })
    // Inline 수정은 Deal updatedAt을 갱신하므로 미업데이트가 풀린다
    expect(b.deal.risk).toBeNull()
  })
})
