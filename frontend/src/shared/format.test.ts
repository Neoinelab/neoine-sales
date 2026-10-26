import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatRelativeTime, formatStamp, nextDay } from './format'

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

/**
 * 시각 표시는 문자열에 붙은 오프셋의 벽시계 그대로다(시간 기준 서버 통일 AC6). 러너(브라우저) 시간대와 무관하다.
 * (계약 변경: 이전 `datetime helpers`의 toLocalInput/fromLocalInput/dayStart는 브라우저 시간대에 의존하고
 * 앱 사용처가 없어 D8에 따라 함수와 테스트를 함께 지웠다.)
 */
describe('formatDateTime', () => {
  it('shows the wall time of the given offset', () => {
    expect(formatDateTime('2026-10-23T00:30:00-05:00')).toBe('2026. 10. 23. 오전 12:30')
  })

  it('keeps the Korean format with the afternoon marker', () => {
    expect(formatDateTime('2026-10-23T15:04:59+09:00')).toBe('2026. 10. 23. 오후 3:04')
  })

  it('shows the UTC wall time for Z', () => {
    expect(formatDateTime('2030-06-14T16:00:00Z')).toBe('2030. 6. 14. 오후 4:00')
  })

  it('does not move the date when the offset day differs from the UTC day', () => {
    expect(formatDateTime('2026-10-23T08:00:00+09:00')).toBe('2026. 10. 23. 오전 8:00') // UTC로는 10월 22일 23:00
  })

  it('accepts the microsecond fraction the server sends', () => {
    expect(formatDateTime('2026-10-23T09:30:00.123456+09:00')).toBe('2026. 10. 23. 오전 9:30')
  })

  it('handles a half-hour offset', () => {
    expect(formatDateTime('2026-10-23T09:30:00+05:30')).toBe('2026. 10. 23. 오전 9:30')
  })
})

describe('formatStamp', () => {
  it('keeps the offset wall time as YYYY-MM-DD HH:mm', () => {
    expect(formatStamp('2026-10-23T15:04:59.123456+09:00')).toBe('2026-10-23 15:04')
  })

  it('does not convert to the UTC date', () => {
    expect(formatStamp('2026-10-23T00:30:00+09:00')).toBe('2026-10-23 00:30')
  })

  it('does not convert to the browser zone for a negative offset', () => {
    expect(formatStamp('2026-10-23T23:30:00-05:00')).toBe('2026-10-23 23:30')
  })

  it('shows the UTC wall time for Z', () => {
    expect(formatStamp('2026-10-23T00:30:00Z')).toBe('2026-10-23 00:30')
  })

  it('accepts a time without fractional seconds', () => {
    expect(formatStamp('2026-01-02T03:04:05+09:00')).toBe('2026-01-02 03:04')
  })
})

describe('unreadable time strings are returned as written', () => {
  // 오프셋 없는 문자열은 브라우저 시간대로 해석하지 않고 원문을 돌려준다(계약).
  const UNREADABLE = ['', 'abc', '2026-10-23', '2026-10-23T09:30:00', '2026-10-23 09:30', '2026-13-45T99:99:99+09:00']

  it.each(UNREADABLE)('formatDateTime returns %j without throwing', (value) => {
    expect(formatDateTime(value)).toBe(value)
  })

  it.each(UNREADABLE)('formatStamp returns %j without throwing', (value) => {
    expect(formatStamp(value)).toBe(value)
  })
})

describe('date parts written in the string offset', () => {
  it('formatDate keeps the calendar date of the string', () => {
    expect(formatDate('2026-10-23T00:30:00+09:00')).toBe('2026-10-23')
    expect(formatDate('2026-10-23T23:30:00-05:00')).toBe('2026-10-23')
  })

  it('formatRelativeTime shows the string date after 30 days', () => {
    expect(formatRelativeTime('2026-08-01T00:30:00+09:00', '2026-10-23T09:30:00+09:00')).toBe('2026-08-01')
    expect(formatRelativeTime('2026-08-01T23:30:00-05:00', '2026-10-23T09:30:00+09:00')).toBe('2026-08-01')
  })
})
