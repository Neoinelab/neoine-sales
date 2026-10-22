import { describe, expect, it } from 'vitest'
import { PAST_PERIOD_LABELS, UPCOMING_PERIOD_LABELS, resolvePeriodChoice } from './periodChoice'
import type { UpdatedPeriods } from './types'

const PRESETS: UpdatedPeriods = {
  today: '2026-10-22',
  periods: [
    { key: '2w', from: '2026-10-08', to: '2026-10-22' },
    { key: '1m', from: '2026-09-22', to: '2026-10-22' },
    { key: '2m', from: '2026-08-22', to: '2026-10-22' },
    { key: '3m', from: '2026-07-22', to: '2026-10-22' },
    { key: '6m', from: '2026-04-22', to: '2026-10-22' },
  ],
  upcoming: [
    { key: '1m', from: '2026-10-22', to: '2026-11-22' },
    { key: '2m', from: '2026-10-22', to: '2026-12-22' },
  ],
}

describe('resolvePeriodChoice', () => {
  it('returns undefined for all and for custom', () => {
    expect(resolvePeriodChoice('', PRESETS)).toBeUndefined()
    expect(resolvePeriodChoice('custom', PRESETS)).toBeUndefined()
  })

  it.each(PRESETS.periods)('resolves the past key $key to the server period', ({ key, from, to }) => {
    expect(resolvePeriodChoice(key, PRESETS)).toEqual({ from, to })
  })

  it('resolves next1m and next2m to the upcoming ranges, not to the past 1m and 2m', () => {
    expect(resolvePeriodChoice('next1m', PRESETS)).toEqual({ from: '2026-10-22', to: '2026-11-22' })
    expect(resolvePeriodChoice('next2m', PRESETS)).toEqual({ from: '2026-10-22', to: '2026-12-22' })
    expect(resolvePeriodChoice('1m', PRESETS)).toEqual({ from: '2026-09-22', to: '2026-10-22' })
  })

  it('returns undefined when the server response lacks the key', () => {
    const partial: UpdatedPeriods = { today: PRESETS.today, periods: [PRESETS.periods[0]!], upcoming: [PRESETS.upcoming[0]!] }

    expect(resolvePeriodChoice('6m', partial)).toBeUndefined()
    expect(resolvePeriodChoice('next2m', partial)).toBeUndefined()
  })
})

describe('period labels', () => {
  it('names the past presets', () => {
    expect(PAST_PERIOD_LABELS).toEqual({
      '2w': '최근 2주',
      '1m': '최근 1개월',
      '2m': '최근 2개월',
      '3m': '최근 3개월',
      '6m': '최근 6개월',
    })
  })

  it('names the upcoming presets', () => {
    expect(UPCOMING_PERIOD_LABELS).toEqual({ '1m': '향후 1개월', '2m': '향후 2개월' })
  })
})
