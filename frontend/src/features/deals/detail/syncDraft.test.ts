import { describe, expect, it } from 'vitest'
import { finalizePlan, planChange, type SyncChange, type SyncResolution, type SyncState } from '../../../shared/model/sync'
import { testCodes } from '../../../shared/model/testing'
import { changeSummary, dropFrom, stateOf, toStatusChanges, type SyncEntry } from './syncDraft'

const codes = testCodes()
const BASE: SyncState = { statusKey: 'price_negotiation', forecastKey: 'commit' }
const CLOSING: SyncResolution = { revenueAmount: 900_000_000, revenueDate: '2026-10-20' }

function entry(state: SyncState, change: SyncChange, resolution?: SyncResolution): SyncEntry {
  const done = finalizePlan(state, planChange(state, change, codes), resolution, codes)
  if (!done.ok) throw new Error(done.message)
  return { change, applied: done.applied }
}

const status = (value: string): SyncChange => ({ field: 'statusKey', value })
const forecast = (value: string): SyncChange => ({ field: 'forecastKey', value })

describe('stateOf', () => {
  // 항목이 없으면 기준 상태를 그대로 돌려준다.
  it('항목이 없으면 기준 상태를 돌려준다', () => {
    // when: 빈 항목으로 상태를 구한다
    const state = stateOf(BASE, [])

    // then: 기준과 같다
    expect(state).toEqual(BASE)
  })

  // 변경 항목의 패치를 순서대로 적용한다.
  it('패치를 순서대로 적용한다', () => {
    // given: Status 변경 뒤 Forecast 변경 항목
    const first = entry(BASE, status('introduction'))
    const second = entry({ statusKey: 'introduction', forecastKey: 'commit' }, forecast('best'))

    // when: 두 항목을 적용한 상태를 구한다
    const state = stateOf(BASE, [first, second])

    // then: Status와 Forecast 변경이 둘 다 반영된다
    expect(state).toEqual({ statusKey: 'introduction', forecastKey: 'best' })
  })

  // 요청한 필드와 함께 바뀐 필드도 상태에 반영된다.
  it('요청한 필드와 함께 바뀐 필드도 반영한다', () => {
    // when: 계약완료로 바꾼 항목의 상태를 구한다
    const state = stateOf(BASE, [entry(BASE, status('contract_completed'), CLOSING)])

    // then: Forecast도 Won이 된다
    expect(state).toEqual({ statusKey: 'contract_completed', forecastKey: 'won' })
  })
})

describe('dropFrom', () => {
  const first = entry(BASE, status('introduction'))
  const second = entry({ statusKey: 'introduction', forecastKey: 'commit' }, forecast('best'))

  // 필드의 항목과 그 뒤 항목을 버리고 함께 버려진 다른 필드를 알려 준다.
  it('필드의 항목과 뒤 항목을 버리고 함께 버려진 필드를 알려 준다', () => {
    // when: 첫 항목의 필드를 버린다
    const result = dropFrom([first, second], 'statusKey')

    // then: 모두 버려지고 Forecast가 함께 버려졌다고 알린다
    expect(result.kept).toEqual([])
    expect(result.alsoDropped).toEqual(['forecastKey'])
  })

  // 뒤 필드를 버려도 앞 항목은 유지한다.
  it('뒤 필드를 버려도 앞 항목은 유지한다', () => {
    // when: 뒤 항목의 필드를 버린다
    const result = dropFrom([first, second], 'forecastKey')

    // then: 첫 항목만 남고 함께 버려진 필드는 없다
    expect(result.kept).toEqual([first])
    expect(result.alsoDropped).toEqual([])
  })

  // 항목이 없는 필드를 버려도 아무것도 바뀌지 않는다.
  it('항목이 없는 필드는 버려도 변화가 없다', () => {
    // when: 항목이 없는 필드를 버린다
    const result = dropFrom([first], 'forecastKey')

    // then: 항목이 그대로고 함께 버려진 필드는 없다
    expect(result.kept).toEqual([first])
    expect(result.alsoDropped).toEqual([])
  })
})

describe('toStatusChanges', () => {
  // 순서를 유지하며 항목마다 자기 해결값으로 바꾼다.
  it('순서를 유지하며 항목마다 자기 해결값으로 바꾼다', () => {
    // given: 계약완료 항목
    const closing = entry(BASE, status('contract_completed'), CLOSING)

    // when: 계약완료 항목을 변경 요청으로 변환한다
    const changes = toStatusChanges([closing])

    // then: 변경 요청과 해결값(Status·Forecast 포함)을 담는다
    expect(changes).toEqual([
      { change: status('contract_completed'), resolution: { revenueAmount: 900_000_000, revenueDate: '2026-10-20', statusKey: 'contract_completed', forecastKey: 'won' } },
    ])
    // given: Forecast 변경 뒤 Status 변경 항목
    const first = entry(BASE, forecast('best'))
    const second = entry({ statusKey: 'price_negotiation', forecastKey: 'best' }, status('introduction'))
    // when: 두 항목을 변환한다
    const ordered = toStatusChanges([first, second]).map((c) => c.change)
    // then: 변경 순서가 유지된다
    expect(ordered).toEqual([forecast('best'), status('introduction')])
  })

  // 항목이 없으면 빈 목록이다.
  it('항목이 없으면 빈 목록이다', () => {
    // when: 빈 항목을 변환한다
    const changes = toStatusChanges([])

    // then: 빈 목록이다
    expect(changes).toEqual([])
  })
})

describe('changeSummary', () => {
  // 두 필드가 모두 기준과 다르면 둘 다 요약에 쓴다.
  it('두 필드가 모두 바뀌면 둘 다 요약한다', () => {
    // when: 계약완료 항목으로 요약한다
    const summary = changeSummary(BASE, [entry(BASE, status('contract_completed'), CLOSING)], codes)

    // then: Status와 Forecast 변경을 모두 말한다
    expect(summary).toBe("Status가 '계약완료'로, Forecast가 'Won'으로 변경되었습니다.")
  })

  // 기준과 다른 필드만 요약하고 Status를 먼저 쓴다.
  it('기준과 다른 필드만 Status 먼저 요약한다', () => {
    // given: Forecast 변경 뒤 Status 변경 항목
    const first = entry(BASE, forecast('best'))
    const second = entry({ statusKey: 'price_negotiation', forecastKey: 'best' }, status('introduction'))

    // when: 두 항목 전체와 Forecast 항목만으로 각각 요약한다
    const both = changeSummary(BASE, [first, second], codes)
    const forecastOnly = changeSummary(BASE, [first], codes)

    // then: 둘 다 바뀌면 Status 먼저, Forecast만 바뀌면 Forecast만 쓴다
    expect(both).toBe("Status가 '제품소개'로, Forecast가 'Best'로 변경되었습니다.")
    expect(forecastOnly).toBe("Forecast가 'Best'로 변경되었습니다.")
  })

  // 기준과 다른 것이 없으면 요약은 없다.
  it('기준과 다른 것이 없으면 요약이 없다', () => {
    // when: 항목이 없을 때와 같은 값으로 바꾼 항목으로 각각 요약한다
    const noEntries = changeSummary(BASE, [], codes)
    const sameValue = changeSummary(BASE, [entry(BASE, status('price_negotiation'))], codes)

    // then: 둘 다 null이다
    expect(noEntries).toBeNull()
    expect(sameValue).toBeNull()
  })
})
