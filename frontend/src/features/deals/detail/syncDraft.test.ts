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
  it('is the base when there are no entries', () => {
    expect(stateOf(BASE, [])).toEqual(BASE)
  })

  it('applies the patches in order', () => {
    const first = entry(BASE, status('introduction'))
    const second = entry({ statusKey: 'introduction', forecastKey: 'commit' }, forecast('best'))

    expect(stateOf(BASE, [first, second])).toEqual({ statusKey: 'introduction', forecastKey: 'best' })
  })

  it('includes the fields that were changed along with the requested one', () => {
    expect(stateOf(BASE, [entry(BASE, status('contract_completed'), CLOSING)])).toEqual({ statusKey: 'contract_completed', forecastKey: 'won' })
  })
})

describe('dropFrom', () => {
  const first = entry(BASE, status('introduction'))
  const second = entry({ statusKey: 'introduction', forecastKey: 'commit' }, forecast('best'))

  it('drops the entry of the field and every later entry, and names the other fields dropped with it', () => {
    const result = dropFrom([first, second], 'statusKey')

    expect(result.kept).toEqual([])
    expect(result.alsoDropped).toEqual(['forecastKey'])
  })

  it('keeps earlier entries when the later field is dropped', () => {
    const result = dropFrom([first, second], 'forecastKey')

    expect(result.kept).toEqual([first])
    expect(result.alsoDropped).toEqual([])
  })

  it('changes nothing for a field that has no entry', () => {
    const result = dropFrom([first], 'forecastKey')

    expect(result.kept).toEqual([first])
    expect(result.alsoDropped).toEqual([])
  })
})

describe('toStatusChanges', () => {
  it('keeps the order and converts each applied result to its own resolution', () => {
    const closing = entry(BASE, status('contract_completed'), CLOSING)

    expect(toStatusChanges([closing])).toEqual([
      { change: status('contract_completed'), resolution: { revenueAmount: 900_000_000, revenueDate: '2026-10-20', statusKey: 'contract_completed', forecastKey: 'won' } },
    ])
    const first = entry(BASE, forecast('best'))
    const second = entry({ statusKey: 'price_negotiation', forecastKey: 'best' }, status('introduction'))
    expect(toStatusChanges([first, second]).map((c) => c.change)).toEqual([forecast('best'), status('introduction')])
  })

  it('is empty without entries', () => {
    expect(toStatusChanges([])).toEqual([])
  })
})

describe('changeSummary', () => {
  it('names both fields when both ended up different from the base', () => {
    const summary = changeSummary(BASE, [entry(BASE, status('contract_completed'), CLOSING)], codes)

    expect(summary).toBe("Status가 '계약완료'로, Forecast가 'Won'으로 변경되었습니다.")
  })

  it('names only the field that differs from the base, Status first', () => {
    const first = entry(BASE, forecast('best'))
    const second = entry({ statusKey: 'price_negotiation', forecastKey: 'best' }, status('introduction'))

    expect(changeSummary(BASE, [first, second], codes)).toBe("Status가 '제품소개'로, Forecast가 'Best'로 변경되었습니다.")
    expect(changeSummary(BASE, [first], codes)).toBe("Forecast가 'Best'로 변경되었습니다.")
  })

  it('is null when nothing differs from the base', () => {
    expect(changeSummary(BASE, [], codes)).toBeNull()
    expect(changeSummary(BASE, [entry(BASE, status('price_negotiation'))], codes)).toBeNull()
  })
})
