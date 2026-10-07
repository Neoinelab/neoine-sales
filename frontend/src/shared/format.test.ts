import { describe, expect, it } from 'vitest'
import { dayStart, formatAmount, fromLocalInput, toLocalInput } from './format'

describe('formatAmount', () => {
  it('groups thousands and keeps the decimals as given', () => {
    expect(formatAmount('150000000', 'KRW')).toBe('150,000,000 KRW')
    expect(formatAmount('1234567.8912', 'USD')).toBe('1,234,567.8912 USD')
    expect(formatAmount('0', 'KRW')).toBe('0 KRW')
  })
})

describe('datetime helpers', () => {
  it('round-trips a datetime-local value', () => {
    const local = '2026-03-02T10:30'

    expect(toLocalInput(fromLocalInput(local))).toBe(local)
  })

  it('sends a timezone-aware instant', () => {
    expect(fromLocalInput('2026-03-02T10:30')).toMatch(/Z$/)
  })

  it('moves a date to the start of a later day', () => {
    const start = new Date(dayStart('2026-03-02'))
    const next = new Date(dayStart('2026-03-02', 1))

    expect(next.getTime() - start.getTime()).toBeGreaterThanOrEqual(23 * 3_600_000)
    expect(start.getHours()).toBe(0)
  })
})
