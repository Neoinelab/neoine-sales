import { describe, expect, it } from 'vitest'
import { finalizePlan, isSyncConsistent, planChange } from './sync'
import { testCodes } from './testing'
import type { Code, CodeSet } from './types'

const codes = testCodes()
const open = { statusKey: 'price_negotiation', forecastKey: 'commit' }
const won = { statusKey: 'contract_completed', forecastKey: 'won' }
const lost = { statusKey: 'price_negotiation', forecastKey: 'lost' }

describe('planChange 규칙표', () => {
  it('T-SYNC-01 Status를 계약완료로 바꾸면 Forecast=Won을 함께 바꾸고 매출 입력을 요구한다', () => {
    const plan = planChange(open, { field: 'statusKey', value: 'contract_completed' }, codes)
    expect(plan.kind).toBe('needRevenue')
    expect(plan).toMatchObject({ patch: { statusKey: 'contract_completed', forecastKey: 'won' } })
    if (plan.kind === 'needRevenue') {
      expect(plan.notice).toContain("Status가 '계약완료'")
      expect(plan.notice).toContain("Forecast가 'Won'")
    }
  })

  it('T-SYNC-02 Forecast를 Won으로 바꾸면 Status=계약완료를 함께 바꾸고 매출 입력을 요구한다', () => {
    const plan = planChange(open, { field: 'forecastKey', value: 'won' }, codes)
    expect(plan.kind).toBe('needRevenue')
    expect(plan).toMatchObject({ patch: { statusKey: 'contract_completed', forecastKey: 'won' } })
  })

  it('T-SYNC-02b Lost에서 Won으로 가는 것도 needRevenue다', () => {
    const plan = planChange(lost, { field: 'forecastKey', value: 'won' }, codes)
    expect(plan.kind).toBe('needRevenue')
  })

  it('T-SYNC-03 Forecast를 Lost로 바꾸면 Status는 그대로 둔다', () => {
    const plan = planChange(open, { field: 'forecastKey', value: 'lost' }, codes)
    expect(plan).toEqual({ kind: 'independent', patch: { forecastKey: 'lost' } })
  })

  it('T-SYNC-04 Won에서 다른 Forecast로 가면 계약완료를 제외한 Status 선택을 요구하고 기본값은 없다', () => {
    const plan = planChange(won, { field: 'forecastKey', value: 'commit' }, codes)
    expect(plan.kind).toBe('askStatus')
    if (plan.kind !== 'askStatus') throw new Error('unexpected')
    expect(plan.defaultKey).toBeNull()
    expect(plan.options).not.toContain('contract_completed')
    expect(plan.options).toHaveLength(6)
    expect(plan.patch).toEqual({ forecastKey: 'commit' })
    expect(plan.prompt).toContain("Forecast를 'Commit'(으)로 바꾸면")
  })

  it('T-SYNC-04b Won에서 Lost로 가도 Status 선택을 요구한다', () => {
    const plan = planChange(won, { field: 'forecastKey', value: 'lost' }, codes)
    expect(plan.kind).toBe('askStatus')
  })

  it('T-SYNC-05 Lost에서 다른 Forecast로 가면 Status를 묻되 기본은 현재 Status다', () => {
    const plan = planChange(lost, { field: 'forecastKey', value: 'best' }, codes)
    expect(plan.kind).toBe('askStatus')
    if (plan.kind !== 'askStatus') throw new Error('unexpected')
    expect(plan.defaultKey).toBe('price_negotiation')
    expect(plan.options).not.toContain('contract_completed')
  })

  it('T-SYNC-06 계약완료에서 이전 단계로 가면 Won 제외 Forecast 선택을 요구한다', () => {
    const plan = planChange(won, { field: 'statusKey', value: 'poc_completed' }, codes)
    expect(plan.kind).toBe('askForecast')
    if (plan.kind !== 'askForecast') throw new Error('unexpected')
    expect(plan.options).toEqual(['pipeline', 'best', 'most_likely', 'commit', 'lost'])
    expect(plan.patch).toEqual({ statusKey: 'poc_completed' })
    expect(plan.prompt).toContain("Status를 'POC완료'로 바꾸면 계약완료가 해제됩니다")
  })

  it('T-SYNC-07 그 외 변경은 독립 변경이다', () => {
    expect(planChange(open, { field: 'statusKey', value: 'poc_completed' }, codes)).toEqual({
      kind: 'independent',
      patch: { statusKey: 'poc_completed' },
    })
    expect(planChange(open, { field: 'forecastKey', value: 'best' }, codes)).toEqual({
      kind: 'independent',
      patch: { forecastKey: 'best' },
    })
  })

  it('T-SYNC-07b 값이 같으면 빈 patch의 독립 변경이다', () => {
    expect(planChange(won, { field: 'forecastKey', value: 'won' }, codes)).toEqual({ kind: 'independent', patch: {} })
    expect(planChange(won, { field: 'statusKey', value: 'contract_completed' }, codes)).toEqual({
      kind: 'independent',
      patch: {},
    })
  })

  it('T-SYNC-08 코드 이름이 바뀌어도 key 기준으로 동작하고 문구는 새 이름을 쓴다', () => {
    const renamed: CodeSet = {
      statuses: codes.statuses.map((c: Code) => (c.key === 'contract_completed' ? { ...c, name: '수주확정' } : c)),
      forecasts: codes.forecasts.map((c: Code) => (c.key === 'won' ? { ...c, name: '성사' } : c)),
    }
    const plan = planChange(open, { field: 'statusKey', value: 'contract_completed' }, renamed)
    expect(plan.kind).toBe('needRevenue')
    if (plan.kind === 'needRevenue') expect(plan.notice).toContain("'수주확정'")
    const back = planChange(won, { field: 'forecastKey', value: 'best' }, renamed)
    expect(back.kind).toBe('askStatus')
  })
})

describe('finalizePlan', () => {
  it('T-SYNC-09a needRevenue는 금액·매출일이 없거나 틀리면 거부한다', () => {
    const plan = planChange(open, { field: 'statusKey', value: 'contract_completed' }, codes)
    for (const resolution of [
      undefined,
      {},
      { revenueAmount: 0, revenueDate: '2026-10-20' },
      { revenueAmount: 1.5, revenueDate: '2026-10-20' },
      { revenueAmount: 1000 },
      { revenueAmount: 1000, revenueDate: '' },
    ]) {
      const result = finalizePlan(open, plan, resolution, codes)
      expect(result).toMatchObject({ ok: false, reason: 'revenue' })
      if (!result.ok) expect(result.message).toBe('Won·계약완료로 바꾸려면 매출금액과 매출일이 필요합니다.')
    }
  })

  it('T-SYNC-09b needRevenue 확정은 함께 바뀐 값과 알림을 만든다', () => {
    const plan = planChange(open, { field: 'statusKey', value: 'contract_completed' }, codes)
    const result = finalizePlan(open, plan, { revenueAmount: 900_000_000, revenueDate: '2026-10-20' }, codes)
    expect(result).toEqual({
      ok: true,
      applied: {
        patch: { statusKey: 'contract_completed', forecastKey: 'won' },
        revenue: { amount: 900_000_000, date: '2026-10-20' },
        coChanged: [{ field: 'forecastKey', from: 'commit', to: 'won' }],
        notice: "Status가 '계약완료'로, Forecast가 'Won'으로 함께 변경되었습니다.",
      },
    })
  })

  it('T-SYNC-09c askStatus는 options 밖 선택을 거부하고 선택하면 Status를 함께 바꾼다', () => {
    const plan = planChange(won, { field: 'forecastKey', value: 'commit' }, codes)
    expect(finalizePlan(won, plan, undefined, codes)).toMatchObject({ ok: false, reason: 'choice' })
    expect(finalizePlan(won, plan, { statusKey: 'contract_completed' }, codes)).toMatchObject({
      ok: false,
      reason: 'choice',
    })
    const result = finalizePlan(won, plan, { statusKey: 'poc_completed' }, codes)
    expect(result).toMatchObject({
      ok: true,
      applied: {
        patch: { forecastKey: 'commit', statusKey: 'poc_completed' },
        revenue: null,
        coChanged: [{ field: 'statusKey', from: 'contract_completed', to: 'poc_completed' }],
      },
    })
    if (result.ok) expect(result.applied.notice).toBe("Status가 'POC완료'로 함께 변경되었습니다.")
  })

  it('T-SYNC-09d askForecast는 Won을 선택하면 거부한다', () => {
    const plan = planChange(won, { field: 'statusKey', value: 'poc_completed' }, codes)
    expect(finalizePlan(won, plan, { forecastKey: 'won' }, codes)).toMatchObject({ ok: false, reason: 'choice' })
    const result = finalizePlan(won, plan, { forecastKey: 'best' }, codes)
    expect(result).toMatchObject({ ok: true, applied: { patch: { statusKey: 'poc_completed', forecastKey: 'best' } } })
  })

  it('T-SYNC-09e Lost에서 되돌릴 때 현재 Status를 그대로 고르면 함께 바뀐 값이 없다', () => {
    const plan = planChange(lost, { field: 'forecastKey', value: 'best' }, codes)
    const result = finalizePlan(lost, plan, { statusKey: 'price_negotiation' }, codes)
    expect(result).toMatchObject({ ok: true, applied: { coChanged: [], notice: null } })
  })

  it('T-SYNC-09f independent는 resolution을 무시한다', () => {
    const plan = planChange(open, { field: 'forecastKey', value: 'best' }, codes)
    expect(finalizePlan(open, plan, { revenueAmount: 5 }, codes)).toEqual({
      ok: true,
      applied: { patch: { forecastKey: 'best' }, revenue: null, coChanged: [], notice: null },
    })
  })
})

describe('isSyncConsistent', () => {
  it('계약완료 ⇔ Won이면 일관적이다', () => {
    expect(isSyncConsistent(won)).toBe(true)
    expect(isSyncConsistent(open)).toBe(true)
    expect(isSyncConsistent({ statusKey: 'contract_completed', forecastKey: 'commit' })).toBe(false)
    expect(isSyncConsistent({ statusKey: 'price_negotiation', forecastKey: 'won' })).toBe(false)
  })
})
