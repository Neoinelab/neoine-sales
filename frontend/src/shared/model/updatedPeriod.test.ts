import { describe, expect, it } from 'vitest'
import { selectedUpdatedPeriod } from './updatedPeriod'
import type { UpdatedPeriods } from './types'

const PERIODS: UpdatedPeriods['periods'] = [
  { key: '2w', from: '2026-10-07', to: '2026-10-21' },
  { key: '1m', from: '2026-09-21', to: '2026-10-21' },
  { key: '2m', from: '2026-08-21', to: '2026-10-21' },
  { key: '3m', from: '2026-07-21', to: '2026-10-21' },
  { key: '6m', from: '2026-04-21', to: '2026-10-21' },
]

describe('selectedUpdatedPeriod (AC-18, AC-19)', () => {
  it('is all when no dates are in the URL', () => {
    expect(selectedUpdatedPeriod(undefined, undefined, PERIODS)).toBe('')
    expect(selectedUpdatedPeriod(undefined, undefined, undefined)).toBe('')
  })

  it.each(PERIODS)('selects the $key preset whose dates match exactly', ({ key, from, to }) => {
    expect(selectedUpdatedPeriod(from, to, PERIODS)).toBe(key)
  })

  it('falls back to custom when only one side is set', () => {
    expect(selectedUpdatedPeriod('2026-10-07', undefined, PERIODS)).toBe('custom')
    expect(selectedUpdatedPeriod(undefined, '2026-10-21', PERIODS)).toBe('custom')
  })

  it('falls back to custom when a date differs by one day or the range is from another day', () => {
    expect(selectedUpdatedPeriod('2026-10-08', '2026-10-21', PERIODS)).toBe('custom')
    expect(selectedUpdatedPeriod('2026-10-07', '2026-10-20', PERIODS)).toBe('custom')
    expect(selectedUpdatedPeriod('2026-10-06', '2026-10-20', PERIODS)).toBe('custom')
  })

  it('is custom while the presets are unknown (loading or failed) and a date is present', () => {
    expect(selectedUpdatedPeriod('2026-10-07', '2026-10-21', undefined)).toBe('custom')
    expect(selectedUpdatedPeriod('2026-10-07', undefined, undefined)).toBe('custom')
    expect(selectedUpdatedPeriod(undefined, '2026-10-21', undefined)).toBe('custom')
  })
})
