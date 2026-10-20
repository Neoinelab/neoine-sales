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
  it('uses the agreed conflict message and no longer exports a duplicate message', async () => {
    const model = await import('./sync')
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
  ])('is true: %s', (_name, start, first, firstResolution, next, resolution) => {
    const { s1, result } = second(start, first, firstResolution, next, resolution)

    expect(overridesRequested(first, s1, result)).toBe(true)
  })

  it('is false when the second change only changes a field the first one changed along with it', () => {
    const first = status('poc_completed')
    const { s1, result } = second(WON, first, { forecastKey: 'commit' }, forecast('best'))

    expect(overridesRequested(first, s1, result)).toBe(false)
  })

  it('is false when a lost reopen chooses the status the first change already set', () => {
    const first = status('introduction')
    const { s1, result } = second(LOST, first, undefined, forecast('commit'), { statusKey: 'introduction' })

    expect(overridesRequested(first, s1, result)).toBe(false)
  })

  it('is true when a lost reopen chooses another status than the first change set', () => {
    const first = status('introduction')
    const { s1, result } = second(LOST, first, undefined, forecast('commit'), { statusKey: 'prospecting' })

    expect(overridesRequested(first, s1, result)).toBe(true)
  })
})

describe('certainlyOverrides: conflicts known before any dialog opens', () => {
  it.each([
    ['closing after a status change', START, status('introduction'), undefined, forecast('won')],
    ['closing by status after a forecast change', START, forecast('best'), undefined, status('contract_completed')],
    ['reopening the status after closing (askStatus cannot keep it)', START, status('contract_completed'), CLOSING, forecast('commit')],
    ['leaving won after choosing won (askForecast cannot keep it)', START, forecast('won'), CLOSING, status('poc_completed')],
  ])('is true: %s', (_name, start, first, firstResolution, next) => {
    const s1 = after(start, applied(start, first, firstResolution))

    expect(certainlyOverrides(first, s1, planChange(s1, next, codes))).toBe(true)
  })

  it('is false for an independent second change', () => {
    const first = status('introduction')
    const s1 = after(START, applied(START, first))

    expect(certainlyOverrides(first, s1, planChange(s1, forecast('best'), codes))).toBe(false)
  })

  it('is false when the choice dialog can still keep the first value (askStatus with the first status in the options)', () => {
    const first = status('introduction')
    const s1 = after(LOST, applied(LOST, first))
    const plan = planChange(s1, forecast('commit'), codes)

    expect(plan.kind).toBe('askStatus')
    expect(certainlyOverrides(first, s1, plan)).toBe(false)
  })
})
