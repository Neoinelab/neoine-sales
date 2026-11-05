import { describe, expect, it } from 'vitest'
import { expiryLevel } from './contractExpiry'

describe('expiryLevel (B8)', () => {
  const today = '2027-03-15'

  it.each([
    ['2027-03-15', 'danger'],
    ['2027-03-31', 'danger'],
    ['2027-04-14', 'danger'],
    ['2027-04-15', 'warning'],
    ['2027-05-14', 'warning'],
    ['2027-05-15', null],
    ['2028-01-01', null],
  ] as const)('issued contract ending %s is %s for both issued statuses (C7)', (end, level) => {
    expect(expiryLevel(end, 'issued_new', today)).toBe(level)
    expect(expiryLevel(end, 'issued_renewal', today)).toBe(level)
  })

  it('treats an already ended issued contract as danger', () => {
    expect(expiryLevel('2027-02-28', 'issued_new', today)).toBe('danger')
    expect(expiryLevel('2027-02-28', 'issued_renewal', today)).toBe('danger')
  })

  it('has no level for ended or not-issued contracts, even with a near end date', () => {
    expect(expiryLevel('2027-03-31', 'ended', today)).toBeNull()
    expect(expiryLevel('2027-03-31', 'not_issued', today)).toBeNull()
  })

  it('has no level without an end date', () => {
    expect(expiryLevel(null, 'issued_renewal', today)).toBeNull()
  })

  it('clamps today + N months to the last day of a short month', () => {
    // 2027-01-31 + 1개월 = 2027-02-28, + 2개월 = 2027-03-31
    expect(expiryLevel('2027-02-27', 'issued_new', '2027-01-31')).toBe('danger')
    expect(expiryLevel('2027-02-28', 'issued_new', '2027-01-31')).toBe('warning')
    expect(expiryLevel('2027-03-30', 'issued_new', '2027-01-31')).toBe('warning')
    expect(expiryLevel('2027-03-31', 'issued_new', '2027-01-31')).toBeNull()
  })
})
