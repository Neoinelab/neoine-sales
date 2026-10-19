import { describe, expect, it } from 'vitest'
import { dayStart, formatDate, formatRelativeTime, fromLocalInput, nextDay, toLocalInput } from './format'

describe('nextDay', () => {
  it('returns the following date across month and year ends', () => {
    expect(nextDay('2026-06-30')).toBe('2026-07-01')
    expect(nextDay('2026-12-31')).toBe('2027-01-01')
    expect(nextDay('2026-06-01')).toBe('2026-06-02')
  })

  it('handles leap days', () => {
    expect(nextDay('2028-02-28')).toBe('2028-02-29')
    expect(nextDay('2028-02-29')).toBe('2028-03-01')
    expect(nextDay('2026-02-28')).toBe('2026-03-01')
  })
})

describe('formatRelativeTime', () => {
  const now = '2026-10-15T12:00:00+09:00'

  it('shows minutes, hours and days ago', () => {
    expect(formatRelativeTime('2026-10-15T11:59:40+09:00', now)).toBe('방금 전')
    expect(formatRelativeTime('2026-10-15T11:30:00+09:00', now)).toBe('30분 전')
    expect(formatRelativeTime('2026-10-15T09:00:00+09:00', now)).toBe('3시간 전')
    expect(formatRelativeTime('2026-10-12T12:00:00+09:00', now)).toBe('3일 전')
  })

  it('falls back to a date after 30 days', () => {
    expect(formatRelativeTime('2026-08-01T12:00:00+09:00', now)).toBe('2026-08-01')
  })

  it('treats a future time as just now', () => {
    expect(formatRelativeTime('2026-10-15T13:00:00+09:00', now)).toBe('방금 전')
  })
})

describe('formatDate', () => {
  it('keeps a YYYY-MM-DD date as is and cuts the time from an ISO instant', () => {
    expect(formatDate('2026-10-15')).toBe('2026-10-15')
    expect(formatDate('2026-10-15T09:30:00+09:00')).toBe('2026-10-15')
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
