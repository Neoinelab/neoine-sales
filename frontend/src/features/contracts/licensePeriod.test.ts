import { describe, expect, it } from 'vitest'
import { licenseEnd } from './licensePeriod'

describe('licenseEnd (B4)', () => {
  it.each([
    ['2026-01-01', 1, 'year', '2026-12-31'],
    ['2026-01-01', 6, 'month', '2026-06-30'],
    ['2026-01-01', 12, 'month', '2026-12-31'],
    ['2026-01-01', 2, 'year', '2027-12-31'],
    ['2026-03-15', 1, 'month', '2026-04-14'],
    ['2026-07-01', 1, 'month', '2026-07-31'],
    ['2026-12-01', 1, 'month', '2026-12-31'],
    ['2026-11-15', 3, 'month', '2027-02-14'],
  ] as const)('%s + %i %s ends on %s', (start, amount, unit, expected) => {
    expect(licenseEnd(start, amount, unit)).toBe(expected)
  })

  it('corrects to the last day of a short month (2026-01-31 + 1개월 = 2026-02-28)', () => {
    expect(licenseEnd('2026-01-31', 1, 'month')).toBe('2026-02-28')
  })
})
