import { describe, expect, it } from 'vitest'
import {
  certainlyOverrides,
  finalizePlan,
  overridesRequested,
  planChange,
  SYNC_CONFLICT_MESSAGE,
  type SyncApplied,
  type SyncChange,
  type SyncResolution,
  type SyncState,
} from './sync'
import { testCodes } from './testing'

const codes = testCodes()
const START: SyncState = { statusKey: 'prospecting', forecastKey: 'pipeline' }
const WON: SyncState = { statusKey: 'contract_completed', forecastKey: 'won' }
const LOST: SyncState = { statusKey: 'prospecting', forecastKey: 'lost' }
const CLOSING: SyncResolution = { revenueAmount: 900_000_000, revenueDate: '2026-10-20' }

const status = (value: string): SyncChange => ({ field: 'statusKey', value })
const forecast = (value: string): SyncChange => ({ field: 'forecastKey', value })

function applied(state: SyncState, change: SyncChange, resolution?: SyncResolution): SyncApplied {
  const done = finalizePlan(state, planChange(state, change, codes), resolution, codes)
  if (!done.ok) throw new Error(done.message)
  return done.applied
}

function after(state: SyncState, result: SyncApplied): SyncState {
  return { statusKey: result.patch.statusKey ?? state.statusKey, forecastKey: result.patch.forecastKey ?? state.forecastKey }
}

/** 첫 변경을 적용한 뒤 두 번째 변경을 판정한다(폼과 서버가 같은 순서로 본다). */
function second(start: SyncState, first: SyncChange, firstResolution: SyncResolution | undefined, next: SyncChange, resolution?: SyncResolution) {
  const s1 = after(start, applied(start, first, firstResolution))
  return { s1, plan: planChange(s1, next, codes), result: applied(s1, next, resolution) }
}

describe('messages (same wording as the server)', () => {
  it('합의한 충돌 문구를 쓰고 중복 문구는 더 이상 내보내지 않는다', async () => {
    // when: 모듈을 읽는다
    const model = await import('./sync')
    // then: 중복 문구 내보내기가 없고 충돌 문구가 합의한 문장이다
    expect('SYNC_DUPLICATE_MESSAGE' in model).toBe(false)
    expect(SYNC_CONFLICT_MESSAGE).toBe('먼저 바꾼 값과 맞지 않는 변경입니다. 먼저 바꾼 값을 되돌린 뒤 다시 선택하세요.')
  })
})

describe('overridesRequested (R3): the second change changes what the first one asked for', () => {
  it.each([
    ['closing after a status change', START, status('introduction'), undefined, forecast('won'), CLOSING],
    ['reopening after closing', START, status('contract_completed'), CLOSING, forecast('commit'), { statusKey: 'poc_completed' }],
    ['closing by status after a forecast change', START, forecast('best'), undefined, status('contract_completed'), CLOSING],
    ['leaving won after choosing won', START, forecast('won'), CLOSING, status('poc_completed'), { forecastKey: 'commit' }],
  ])('덮어쓰는 변경이다: %s', (_name, start, first, firstResolution, next, resolution) => {
    // when: 첫 변경을 적용한 뒤 두 번째 변경을 판정한다
    const { s1, result } = second(start, first, firstResolution, next, resolution)

    // then: 두 번째 변경이 첫 변경이 요청한 값을 바꾼다
    expect(overridesRequested(first, s1, result)).toBe(true)
  })

  it('두 번째 변경이 첫 변경과 함께 바뀐 필드만 바꾸면 덮어쓰지 않는다', () => {
    // given: Won 상태에서 Status를 바꾸며 Forecast도 함께 바꾼 첫 변경
    const first = status('poc_completed')

    // when: 두 번째로 Forecast를 best로 바꾼다
    const { s1, result } = second(WON, first, { forecastKey: 'commit' }, forecast('best'))

    // then: 덮어쓰지 않는다
    expect(overridesRequested(first, s1, result)).toBe(false)
  })

  it('Lost를 다시 열 때 첫 변경이 정한 Status를 고르면 덮어쓰지 않는다', () => {
    // given: Lost 상태에서 Status를 introduction으로 바꾼 첫 변경
    const first = status('introduction')

    // when: Forecast를 commit으로 바꾸며 같은 Status를 고른다
    const { s1, result } = second(LOST, first, undefined, forecast('commit'), { statusKey: 'introduction' })

    // then: 덮어쓰지 않는다
    expect(overridesRequested(first, s1, result)).toBe(false)
  })

  it('Lost를 다시 열 때 첫 변경과 다른 Status를 고르면 덮어쓴다', () => {
    // given: Lost 상태에서 Status를 introduction으로 바꾼 첫 변경
    const first = status('introduction')

    // when: Forecast를 commit으로 바꾸며 다른 Status를 고른다
    const { s1, result } = second(LOST, first, undefined, forecast('commit'), { statusKey: 'prospecting' })

    // then: 덮어쓴다
    expect(overridesRequested(first, s1, result)).toBe(true)
  })
})

describe('certainlyOverrides: conflicts known before any dialog opens', () => {
  it.each([
    ['closing after a status change', START, status('introduction'), undefined, forecast('won')],
    ['closing by status after a forecast change', START, forecast('best'), undefined, status('contract_completed')],
    ['reopening the status after closing (askStatus cannot keep it)', START, status('contract_completed'), CLOSING, forecast('commit')],
    ['leaving won after choosing won (askForecast cannot keep it)', START, forecast('won'), CLOSING, status('poc_completed')],
  ])('덮어쓰는 것이 확실하다: %s', (_name, start, first, firstResolution, next) => {
    // when: 첫 변경을 적용한 뒤 두 번째 변경의 계획을 세운다
    const s1 = after(start, applied(start, first, firstResolution))
    const plan = planChange(s1, next, codes)

    // then: 창을 열기 전에 덮어쓰는 것이 확실하다
    expect(certainlyOverrides(first, s1, plan)).toBe(true)
  })

  it('서로 무관한 두 번째 변경은 덮어쓰지 않는 것이 확실하다', () => {
    // given: Status를 바꾼 첫 변경
    const first = status('introduction')
    const s1 = after(START, applied(START, first))

    // when: 두 번째로 Forecast를 best로 바꾸는 계획을 세운다
    const plan = planChange(s1, forecast('best'), codes)

    // then: 덮어쓰는 것이 확실하지 않다
    expect(certainlyOverrides(first, s1, plan)).toBe(false)
  })

  it('선택 창이 첫 값을 유지할 수 있으면 덮어쓰는 것이 확실하지 않다', () => {
    // given: Lost 상태에서 Status를 introduction으로 바꾼 첫 변경
    const first = status('introduction')
    const s1 = after(LOST, applied(LOST, first))
    // when: Forecast를 commit으로 바꾸는 계획을 세운다
    const plan = planChange(s1, forecast('commit'), codes)

    // then: Status를 묻는 창이 열리고 덮어쓰는 것이 확실하지 않다
    expect(plan.kind).toBe('askStatus')
    expect(certainlyOverrides(first, s1, plan)).toBe(false)
  })
})
