import { describe, expect, it } from 'vitest'
import { DEFAULT_STALE_DAYS } from './constants'
import { computeRisk, statusDays } from './risk'

const NOW = '2026-10-15T09:00:00+09:00'
const STALE = 14

describe('computeRisk', () => {
  const base = { forecastKey: 'commit', dueDate: '2026-10-20', lastUpdatedAt: '2026-10-14T10:00:00+09:00' }

  it('T-RISK-01 Due가 오늘이면 기한초과가 아니다', () => {
    expect(computeRisk({ ...base, dueDate: '2026-10-15' }, NOW, STALE)).toBeNull()
  })

  it('T-RISK-02 Due가 어제면 기한초과다', () => {
    expect(computeRisk({ ...base, dueDate: '2026-10-14' }, NOW, STALE)).toBe('overdue')
  })

  it('T-RISK-03 마지막 갱신 14일째는 미업데이트, 13일째는 정상이다', () => {
    expect(computeRisk({ ...base, lastUpdatedAt: '2026-10-01T10:00:00+09:00' }, NOW, STALE)).toBe('stale')
    expect(computeRisk({ ...base, lastUpdatedAt: '2026-10-02T10:00:00+09:00' }, NOW, STALE)).toBeNull()
  })

  it('T-RISK-04 둘 다면 overdue_stale이다', () => {
    expect(computeRisk({ ...base, dueDate: '2026-10-01', lastUpdatedAt: '2026-09-20T10:00:00+09:00' }, NOW, STALE)).toBe(
      'overdue_stale',
    )
  })

  it('T-RISK-05 Won·Lost 종결 Deal은 항상 risk가 없다', () => {
    const stale = { dueDate: '2026-01-01', lastUpdatedAt: '2026-01-01T00:00:00+09:00' }
    expect(computeRisk({ forecastKey: 'won', ...stale }, NOW, STALE)).toBeNull()
    expect(computeRisk({ forecastKey: 'lost', ...stale }, NOW, STALE)).toBeNull()
  })

  it('Action이 없어 dueDate가 null이면 기한초과가 아니다', () => {
    expect(computeRisk({ ...base, dueDate: null }, NOW, STALE)).toBeNull()
  })

  it('오늘은 now 문자열의 달력 날짜를 쓴다(UTC로 바꾸지 않는다)', () => {
    expect(computeRisk({ ...base, dueDate: '2026-10-14' }, '2026-10-15T00:30:00+09:00', STALE)).toBe('overdue')
  })

  it('uses the given staleDays: 7 days is stale at a 7-day threshold, 6 days is not', () => {
    expect(computeRisk({ ...base, lastUpdatedAt: '2026-10-08T10:00:00+09:00' }, NOW, 7)).toBe('stale')
    expect(computeRisk({ ...base, lastUpdatedAt: '2026-10-09T10:00:00+09:00' }, NOW, 7)).toBeNull()
  })

  it('treats a 14-day-old deal as healthy at a 30-day threshold and stale at 1', () => {
    const old = { ...base, lastUpdatedAt: '2026-10-01T10:00:00+09:00' }
    expect(computeRisk(old, NOW, 30)).toBeNull()
    expect(computeRisk({ ...base, lastUpdatedAt: '2026-10-14T10:00:00+09:00' }, NOW, 1)).toBe('stale')
    expect(computeRisk({ ...base, lastUpdatedAt: '2026-10-15T01:00:00+09:00' }, NOW, 1)).toBeNull()
  })

  it('combines overdue with the custom threshold', () => {
    const input = { ...base, dueDate: '2026-10-01', lastUpdatedAt: '2026-10-08T10:00:00+09:00' }
    expect(computeRisk(input, NOW, 7)).toBe('overdue_stale')
    expect(computeRisk(input, NOW, 8)).toBe('overdue')
  })

  it('keeps closed deals null whatever the threshold', () => {
    expect(computeRisk({ forecastKey: 'won', dueDate: '2020-01-01', lastUpdatedAt: '2020-01-01T00:00:00+09:00' }, NOW, 1)).toBeNull()
  })

  it('keeps the mock default threshold at 14', () => {
    expect(DEFAULT_STALE_DAYS).toBe(14)
  })
})

describe('statusDays', () => {
  it('is 0 on the entry day and counts calendar days after it', () => {
    expect(statusDays('2026-10-15T00:01:00+09:00', NOW)).toBe(0)
    expect(statusDays('2026-10-14T23:59:00+09:00', NOW)).toBe(1)
    expect(statusDays('2026-10-10T09:00:00+09:00', NOW)).toBe(5)
  })

  it('never goes below 0 when the entry time is after now', () => {
    expect(statusDays('2026-10-20T09:00:00+09:00', NOW)).toBe(0)
  })

  it('uses the calendar date of the strings, not UTC', () => {
    expect(statusDays('2026-10-14T23:30:00+09:00', '2026-10-15T00:30:00+09:00')).toBe(1)
  })
})
