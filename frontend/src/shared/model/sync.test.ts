import { describe, expect, it } from 'vitest'
import { finalizePlan, isSyncConsistent, planChange } from './sync'
import { testCodes } from './testing'
import type { Code, CodeSet } from './types'

const codes = testCodes()
const open = { statusKey: 'price_negotiation', forecastKey: 'commit' }
const won = { statusKey: 'contract_completed', forecastKey: 'won' }
const lost = { statusKey: 'price_negotiation', forecastKey: 'lost' }

describe('planChange 규칙표', () => {
  // Status를 계약완료로 바꾸면 Forecast도 Won으로 두고 매출 입력을 요구한다(DD-R6).
  // 테스트 코드: DD-114
  it('T-SYNC-01 Status를 계약완료로 바꾸면 Forecast=Won을 함께 바꾸고 매출 입력을 요구한다', () => {
    // when: Status를 계약완료로 바꾸는 계획을 세운다 (전제: 진행 중인 상태(가격협상·Commit))
    const plan = planChange(open, { field: 'statusKey', value: 'contract_completed' }, codes)

    // then: 매출 필요 계획이고 패치와 알림에 두 값이 있다
    expect(plan.kind).toBe('needRevenue')
    expect(plan).toMatchObject({ patch: { statusKey: 'contract_completed', forecastKey: 'won' } })
    if (plan.kind === 'needRevenue') {
      expect(plan.notice).toContain("Status가 '계약완료'")
      expect(plan.notice).toContain("Forecast가 'Won'")
    }
  })

  // Forecast를 Won으로 바꾸면 Status도 계약완료로 두고 매출 입력을 요구한다.
  // 테스트 코드: DD-114
  it('T-SYNC-02 Forecast를 Won으로 바꾸면 Status=계약완료를 함께 바꾸고 매출 입력을 요구한다', () => {
    // when: Forecast를 Won으로 바꾸는 계획을 세운다 (전제: 진행 중인 상태)
    const plan = planChange(open, { field: 'forecastKey', value: 'won' }, codes)

    // then: 매출 필요 계획이고 패치가 계약완료+Won이다
    expect(plan.kind).toBe('needRevenue')
    expect(plan).toMatchObject({ patch: { statusKey: 'contract_completed', forecastKey: 'won' } })
  })

  // Lost에서 Won으로 가는 것도 매출을 요구한다.
  // 테스트 코드: DD-114
  it('T-SYNC-02b Lost에서 Won으로 가는 것도 needRevenue다', () => {
    // when: Forecast를 Won으로 바꾸는 계획을 세운다 (전제: Lost 상태)
    const plan = planChange(lost, { field: 'forecastKey', value: 'won' }, codes)

    // then: 매출 필요 계획이다
    expect(plan.kind).toBe('needRevenue')
  })

  // Forecast를 Lost로 바꾸면 Status는 그대로 둔다.
  // 테스트 코드: DD-114
  it('T-SYNC-03 Forecast를 Lost로 바꾸면 Status는 그대로 둔다', () => {
    // when: Forecast를 Lost로 바꾸는 계획을 세운다 (전제: 진행 중인 상태)
    const plan = planChange(open, { field: 'forecastKey', value: 'lost' }, codes)

    // then: Forecast만 바꾸는 독립 변경이다
    expect(plan).toEqual({ kind: 'independent', patch: { forecastKey: 'lost' } })
  })

  // Won에서 다른 Forecast로 가면 계약완료를 뺀 Status 선택을 기본값 없이 요구한다.
  // 테스트 코드: DD-114
  it('T-SYNC-04 Won에서 다른 Forecast로 가면 계약완료를 제외한 Status 선택을 요구하고 기본값은 없다', () => {
    // when: Forecast를 Commit으로 바꾸는 계획을 세운다 (전제: Won 상태)
    const plan = planChange(won, { field: 'forecastKey', value: 'commit' }, codes)

    // then: Status 선택 계획이고 선택지에 계약완료가 없으며 기본값이 없다
    expect(plan.kind).toBe('askStatus')
    if (plan.kind !== 'askStatus') throw new Error('unexpected')
    expect(plan.defaultKey).toBeNull()
    expect(plan.options).not.toContain('contract_completed')
    expect(plan.options).toHaveLength(6)
    expect(plan.patch).toEqual({ forecastKey: 'commit' })
    expect(plan.prompt).toContain("Forecast를 'Commit'(으)로 바꾸면")
  })

  // Won에서 Lost로 가도 Status 선택을 요구한다.
  // 테스트 코드: DD-114
  it('T-SYNC-04b Won에서 Lost로 가도 Status 선택을 요구한다', () => {
    // when: Forecast를 Lost로 바꾸는 계획을 세운다 (전제: Won 상태)
    const plan = planChange(won, { field: 'forecastKey', value: 'lost' }, codes)

    // then: Status 선택 계획이다
    expect(plan.kind).toBe('askStatus')
  })

  // Lost에서 다른 Forecast로 가면 Status를 묻되 기본은 현재 Status다.
  // 테스트 코드: DD-114
  it('T-SYNC-05 Lost에서 다른 Forecast로 가면 Status를 묻되 기본은 현재 Status다', () => {
    // when: Forecast를 Best로 바꾸는 계획을 세운다 (전제: Lost 상태)
    const plan = planChange(lost, { field: 'forecastKey', value: 'best' }, codes)

    // then: Status 선택 계획이고 기본값이 현재 Status다
    expect(plan.kind).toBe('askStatus')
    if (plan.kind !== 'askStatus') throw new Error('unexpected')
    expect(plan.defaultKey).toBe('price_negotiation')
    expect(plan.options).not.toContain('contract_completed')
  })

  // 계약완료에서 이전 단계로 가면 Won을 뺀 Forecast 선택을 요구한다.
  // 테스트 코드: DD-114
  it('T-SYNC-06 계약완료에서 이전 단계로 가면 Won 제외 Forecast 선택을 요구한다', () => {
    // when: Status를 POC완료로 바꾸는 계획을 세운다 (전제: 계약완료·Won 상태)
    const plan = planChange(won, { field: 'statusKey', value: 'poc_completed' }, codes)

    // then: Forecast 선택 계획이고 선택지에 Won이 없다
    expect(plan.kind).toBe('askForecast')
    if (plan.kind !== 'askForecast') throw new Error('unexpected')
    expect(plan.options).toEqual(['pipeline', 'best', 'most_likely', 'commit', 'lost'])
    expect(plan.patch).toEqual({ statusKey: 'poc_completed' })
    expect(plan.prompt).toContain("Status를 'POC완료'로 바꾸면 계약완료가 해제됩니다")
  })

  // 그 밖의 변경은 독립 변경이다.
  // 테스트 코드: DD-114
  it('T-SYNC-07 그 외 변경은 독립 변경이다', () => {
    // when: 일반 Status·Forecast로 바꾸는 계획을 세운다 (전제: 진행 중인 상태)
    const statusPlan = planChange(open, { field: 'statusKey', value: 'poc_completed' }, codes)
    const forecastPlan = planChange(open, { field: 'forecastKey', value: 'best' }, codes)

    // then: 요청한 값만 담은 독립 변경이다
    expect(statusPlan).toEqual({
      kind: 'independent',
      patch: { statusKey: 'poc_completed' },
    })
    expect(forecastPlan).toEqual({
      kind: 'independent',
      patch: { forecastKey: 'best' },
    })
  })

  // 값이 같으면 빈 패치의 독립 변경이다.
  // 테스트 코드: DD-114
  it('T-SYNC-07b 값이 같으면 빈 patch의 독립 변경이다', () => {
    // when: 같은 값으로 바꾸는 계획을 세운다 (전제: 각 상태)
    const forecastPlan = planChange(won, { field: 'forecastKey', value: 'won' }, codes)
    const statusPlan = planChange(won, { field: 'statusKey', value: 'contract_completed' }, codes)

    // then: 빈 패치의 독립 변경이다
    expect(forecastPlan).toEqual({ kind: 'independent', patch: {} })
    expect(statusPlan).toEqual({
      kind: 'independent',
      patch: {},
    })
  })

  // 코드 이름이 바뀌어도 key 기준으로 동작하고 문구는 새 이름을 쓴다.
  // 테스트 코드: DD-114
  it('T-SYNC-08 코드 이름이 바뀌어도 key 기준으로 동작하고 문구는 새 이름을 쓴다', () => {
    // given: 이름을 바꾼 코드 목록
    const renamed: CodeSet = {
      statuses: codes.statuses.map((c: Code) => (c.key === 'contract_completed' ? { ...c, name: '수주확정' } : c)),
      forecasts: codes.forecasts.map((c: Code) => (c.key === 'won' ? { ...c, name: '성사' } : c)),
    }

    // when: 종결 계획을 세우고 확정한다
    const plan = planChange(open, { field: 'statusKey', value: 'contract_completed' }, renamed)

    // then: 규칙은 그대로이고 알림이 새 이름이다
    expect(plan.kind).toBe('needRevenue')
    if (plan.kind === 'needRevenue') expect(plan.notice).toContain("'수주확정'")
    const back = planChange(won, { field: 'forecastKey', value: 'best' }, renamed)
    expect(back.kind).toBe('askStatus')
  })
})

describe('finalizePlan', () => {
  // 종결 답에 금액·매출일이 없거나 틀리면 거부한다.
  // 테스트 코드: DD-114
  it('T-SYNC-09a needRevenue는 금액·매출일이 없거나 틀리면 거부한다', () => {
    // when: 금액·날짜가 빠졌거나 틀린 답으로 확정한다 (전제: 계약완료로 바꾸는 계획)
    const plan = planChange(open, { field: 'statusKey', value: 'contract_completed' }, codes)

    // then: 매출 사유의 거부와 '매출금액과 매출일이 필요합니다' 문구다
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

  // 종결 확정은 함께 바뀐 값과 알림을 만든다.
  // 테스트 코드: DD-114
  it('T-SYNC-09b needRevenue 확정은 함께 바뀐 값과 알림을 만든다', () => {
    // given: 계약완료로 바꾸는 계획
    const plan = planChange(open, { field: 'statusKey', value: 'contract_completed' }, codes)

    // when: 매출금액·매출일 답으로 확정한다
    const result = finalizePlan(open, plan, { revenueAmount: 900_000_000, revenueDate: '2026-10-20' }, codes)

    // then: 적용 결과에 패치, 매출, 함께 바뀐 Forecast, 알림이 있다
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

  // Status 선택 답은 선택지 밖이면 거부하고 고르면 Status를 함께 바꾼다.
  // 테스트 코드: DD-114
  it('T-SYNC-09c askStatus는 options 밖 선택을 거부하고 선택하면 Status를 함께 바꾼다', () => {
    // when: 답 없음, 계약완료, POC완료로 각각 확정한다 (전제: Won에서 Commit으로 바꾸는 계획)
    const plan = planChange(won, { field: 'forecastKey', value: 'commit' }, codes)

    // then: 앞의 둘은 선택 사유의 거부, 마지막은 Status를 함께 바꾸고 알림이 나온다
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

  // Forecast 선택 답이 Won이면 거부한다.
  // 테스트 코드: DD-114
  it('T-SYNC-09d askForecast는 Won을 선택하면 거부한다', () => {
    // when: Won, Best로 각각 확정한다 (전제: 계약완료에서 POC완료로 바꾸는 계획)
    const plan = planChange(won, { field: 'statusKey', value: 'poc_completed' }, codes)

    // then: Won은 거부되고 Best는 적용된다
    expect(finalizePlan(won, plan, { forecastKey: 'won' }, codes)).toMatchObject({ ok: false, reason: 'choice' })
    const result = finalizePlan(won, plan, { forecastKey: 'best' }, codes)
    expect(result).toMatchObject({ ok: true, applied: { patch: { statusKey: 'poc_completed', forecastKey: 'best' } } })
  })

  // Lost에서 되돌리며 현재 Status를 그대로 고르면 함께 바뀐 값이 없다.
  // 테스트 코드: DD-114
  it('T-SYNC-09e Lost에서 되돌릴 때 현재 Status를 그대로 고르면 함께 바뀐 값이 없다', () => {
    // given: Lost에서 Best로 바꾸는 계획
    const plan = planChange(lost, { field: 'forecastKey', value: 'best' }, codes)

    // when: 현재 Status를 골라 확정한다
    const result = finalizePlan(lost, plan, { statusKey: 'price_negotiation' }, codes)

    // then: 함께 바뀐 값이 없고 알림이 null이다
    expect(result).toMatchObject({ ok: true, applied: { coChanged: [], notice: null } })
  })

  // 독립 변경은 함께 준 답을 무시한다.
  // 테스트 코드: DD-114
  it('T-SYNC-09f independent는 resolution을 무시한다', () => {
    // when: 매출 답을 함께 주고 확정한다 (전제: Forecast를 Best로 바꾸는 독립 계획)
    const plan = planChange(open, { field: 'forecastKey', value: 'best' }, codes)

    // then: 요청한 값만 바뀌고 매출·함께 바뀐 값·알림이 없다
    expect(finalizePlan(open, plan, { revenueAmount: 5 }, codes)).toEqual({
      ok: true,
      applied: { patch: { forecastKey: 'best' }, revenue: null, coChanged: [], notice: null },
    })
  })
})

describe('isSyncConsistent', () => {
  // 계약완료와 Won이 함께이거나 둘 다 아니면 일관적이다.
  // 테스트 코드: DD-114
  it('계약완료 ⇔ Won이면 일관적이다', () => {
    // when: 일관성을 판정한다 (전제: 여러 Status·Forecast 조합)
    const actual1 = isSyncConsistent(won)
    const actual2 = isSyncConsistent(open)
    const actual3 = isSyncConsistent({ statusKey: 'contract_completed', forecastKey: 'commit' })
    const actual4 = isSyncConsistent({ statusKey: 'price_negotiation', forecastKey: 'won' })

    // then: 계약완료+Won과 둘 다 아닌 조합만 일관적이다
    expect(actual1).toBe(true)
    expect(actual2).toBe(true)
    expect(actual3).toBe(false)
    expect(actual4).toBe(false)
  })
})
