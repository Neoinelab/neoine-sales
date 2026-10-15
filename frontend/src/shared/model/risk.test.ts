import { describe, expect, it } from 'vitest'
import { computeRisk } from './risk'

const NOW = '2026-10-15T09:00:00+09:00'

describe('computeRisk', () => {
  const base = { forecastKey: 'commit', dueDate: '2026-10-20', lastUpdatedAt: '2026-10-14T10:00:00+09:00' }

  it('T-RISK-01 Due가 오늘이면 기한초과가 아니다', () => {
    expect(computeRisk({ ...base, dueDate: '2026-10-15' }, NOW)).toBeNull()
  })

  it('T-RISK-02 Due가 어제면 기한초과다', () => {
    expect(computeRisk({ ...base, dueDate: '2026-10-14' }, NOW)).toBe('overdue')
  })

  it('T-RISK-03 마지막 갱신 14일째는 미업데이트, 13일째는 정상이다', () => {
    expect(computeRisk({ ...base, lastUpdatedAt: '2026-10-01T10:00:00+09:00' }, NOW)).toBe('stale')
    expect(computeRisk({ ...base, lastUpdatedAt: '2026-10-02T10:00:00+09:00' }, NOW)).toBeNull()
  })

  it('T-RISK-04 둘 다면 overdue_stale이다', () => {
    expect(computeRisk({ ...base, dueDate: '2026-10-01', lastUpdatedAt: '2026-09-20T10:00:00+09:00' }, NOW)).toBe(
      'overdue_stale',
    )
  })

  it('T-RISK-05 Won·Lost 종결 Deal은 항상 risk가 없다', () => {
    const stale = { dueDate: '2026-01-01', lastUpdatedAt: '2026-01-01T00:00:00+09:00' }
    expect(computeRisk({ forecastKey: 'won', ...stale }, NOW)).toBeNull()
    expect(computeRisk({ forecastKey: 'lost', ...stale }, NOW)).toBeNull()
  })

  it('Action이 없어 dueDate가 null이면 기한초과가 아니다', () => {
    expect(computeRisk({ ...base, dueDate: null }, NOW)).toBeNull()
  })

  it('오늘은 now 문자열의 달력 날짜를 쓴다(UTC로 바꾸지 않는다)', () => {
    expect(computeRisk({ ...base, dueDate: '2026-10-14' }, '2026-10-15T00:30:00+09:00')).toBe('overdue')
  })
})
