import { describe, expect, it } from 'vitest'
import { formatDate, formatDateTime, formatRelativeDays, formatRelativeTime, formatStamp, nextDay } from './format'

describe('nextDay', () => {
  // 다음 날 계산은 월말·연말을 넘긴다.
  // 테스트 코드: TM-042
  it('returns the following date across month and year ends', () => {
    // when·then: 월말·연말·월초의 다음 날
    expect(nextDay('2026-06-30')).toBe('2026-07-01')
    expect(nextDay('2026-12-31')).toBe('2027-01-01')
    expect(nextDay('2026-06-01')).toBe('2026-06-02')
  })

  // 윤일을 포함해 달력만 쓴다.
  // 테스트 코드: TM-042
  it('handles leap days', () => {
    // when·then: 윤년 2월 28·29일과 평년 2월 28일의 다음 날
    expect(nextDay('2028-02-28')).toBe('2028-02-29')
    expect(nextDay('2028-02-29')).toBe('2028-03-01')
    expect(nextDay('2026-02-28')).toBe('2026-03-01')
  })
})

describe('formatRelativeTime', () => {
  const now = '2026-10-15T12:00:00+09:00'

  // 상대 시각은 방금 전·분·시간·일 전으로 보인다.
  // 테스트 코드: TM-041
  it('shows minutes, hours and days ago', () => {
    // when·then: 20초·30분·3시간·3일 전
    expect(formatRelativeTime('2026-10-15T11:59:40+09:00', now)).toBe('방금 전')
    expect(formatRelativeTime('2026-10-15T11:30:00+09:00', now)).toBe('30분 전')
    expect(formatRelativeTime('2026-10-15T09:00:00+09:00', now)).toBe('3시간 전')
    expect(formatRelativeTime('2026-10-12T12:00:00+09:00', now)).toBe('3일 전')
  })

  // 30일 이상은 날짜로 보인다.
  // 테스트 코드: TM-041
  it('falls back to a date after 30 days', () => {
    // when·then: 2026-08-01은 날짜 문자열
    expect(formatRelativeTime('2026-08-01T12:00:00+09:00', now)).toBe('2026-08-01')
  })

  // 미래 시각은 방금 전이다.
  // 테스트 코드: TM-041
  it('treats a future time as just now', () => {
    // when·then: 1시간 뒤 시각
    expect(formatRelativeTime('2026-10-15T13:00:00+09:00', now)).toBe('방금 전')
  })
})

describe('formatRelativeDays', () => {
  // 시계는 시각(ISO)이지만 비교는 달력 날짜만 쓴다: 같은 날 오늘, 하루 전 어제, 2~29일 N일 전.
  const now = '2026-10-15T00:10:00+09:00'

  // 오늘·어제·N일 전으로 보이고 시·분 단위 표기는 쓰지 않는다.
  it('shows 오늘, 어제 and N일 전 by calendar days only', () => {
    // when·then: 같은 날, 하루 전, 3일 전, 29일 전
    expect(formatRelativeDays('2026-10-15', now)).toBe('오늘')
    expect(formatRelativeDays('2026-10-14', now)).toBe('어제')
    expect(formatRelativeDays('2026-10-12', now)).toBe('3일 전')
    expect(formatRelativeDays('2026-09-16', now)).toBe('29일 전')
  })

  // 30일 이상은 날짜 그대로 보이고, 미래 날짜는 오늘이다.
  it('falls back to the date from 30 days on and treats a future date as 오늘', () => {
    // when·then: 30일 전, 미래 날짜
    expect(formatRelativeDays('2026-09-15', now)).toBe('2026-09-15')
    expect(formatRelativeDays('2026-10-20', now)).toBe('오늘')
  })
})

describe('formatDate', () => {
  // 날짜는 그대로, 시각은 문자열에 적힌 날짜를 보인다.
  // 테스트 코드: TM-039
  it('keeps a YYYY-MM-DD date as is and cuts the time from an ISO instant', () => {
    // when·then: 날짜와 시각 문자열
    expect(formatDate('2026-10-15')).toBe('2026-10-15')
    expect(formatDate('2026-10-15T09:30:00+09:00')).toBe('2026-10-15')
  })
})

/**
 * 시각 표시는 문자열에 붙은 오프셋의 벽시계 그대로다. 러너(브라우저) 시간대와 무관하다.
 */
describe('formatDateTime', () => {
  // 음수 오프셋 시각도 문자열의 벽시계를 보인다.
  // 테스트 코드: TM-039
  it('shows the wall time of the given offset', () => {
    // when·then: -05:00 00:30은 오전 12:30
    expect(formatDateTime('2026-10-23T00:30:00-05:00')).toBe('2026. 10. 23. 오전 12:30')
  })

  // 한국어 형식과 오후 표기를 쓴다.
  // 테스트 코드: TM-039
  it('keeps the Korean format with the afternoon marker', () => {
    // when·then: 15:04는 오후 3:04
    expect(formatDateTime('2026-10-23T15:04:59+09:00')).toBe('2026. 10. 23. 오후 3:04')
  })

  // Z는 UTC 벽시계 그대로다.
  // 테스트 코드: TM-039
  it('shows the UTC wall time for Z', () => {
    // when·then: 16:00Z는 오후 4:00
    expect(formatDateTime('2030-06-14T16:00:00Z')).toBe('2030. 6. 14. 오후 4:00')
  })

  // UTC 날짜로 옮기지 않는다.
  // 테스트 코드: TM-039
  it('does not move the date when the offset day differs from the UTC day', () => {
    // when·then: UTC로는 10월 22일 23:00이지만 문자열의 날짜를 그대로 보인다
    expect(formatDateTime('2026-10-23T08:00:00+09:00')).toBe('2026. 10. 23. 오전 8:00')
  })

  // 서버가 보내는 소수 초를 읽는다.
  // 테스트 코드: TM-039
  it('accepts the microsecond fraction the server sends', () => {
    // when·then: 마이크로초가 있는 시각
    expect(formatDateTime('2026-10-23T09:30:00.123456+09:00')).toBe('2026. 10. 23. 오전 9:30')
  })

  // 30분 단위 오프셋도 벽시계 그대로다.
  // 테스트 코드: TM-039
  it('handles a half-hour offset', () => {
    // when·then: +05:30
    expect(formatDateTime('2026-10-23T09:30:00+05:30')).toBe('2026. 10. 23. 오전 9:30')
  })
})

describe('formatStamp', () => {
  // YYYY-MM-DD HH:mm 형식으로 보인다.
  // 테스트 코드: TM-039
  it('keeps the offset wall time as YYYY-MM-DD HH:mm', () => {
    // when·then: 소수 초가 있는 시각
    expect(formatStamp('2026-10-23T15:04:59.123456+09:00')).toBe('2026-10-23 15:04')
  })

  // UTC 날짜로 바꾸지 않는다.
  // 테스트 코드: TM-039
  it('does not convert to the UTC date', () => {
    // when·then: +09:00 00:30
    expect(formatStamp('2026-10-23T00:30:00+09:00')).toBe('2026-10-23 00:30')
  })

  // 음수 오프셋도 브라우저 시간대로 바꾸지 않는다.
  // 테스트 코드: TM-039
  it('does not convert to the browser zone for a negative offset', () => {
    // when·then: -05:00 23:30
    expect(formatStamp('2026-10-23T23:30:00-05:00')).toBe('2026-10-23 23:30')
  })

  // Z는 UTC 벽시계 그대로다.
  // 테스트 코드: TM-039
  it('shows the UTC wall time for Z', () => {
    // when·then: 00:30Z
    expect(formatStamp('2026-10-23T00:30:00Z')).toBe('2026-10-23 00:30')
  })

  // 소수 초가 없어도 읽는다.
  // 테스트 코드: TM-039
  it('accepts a time without fractional seconds', () => {
    // when·then: 소수 초 없는 시각
    expect(formatStamp('2026-01-02T03:04:05+09:00')).toBe('2026-01-02 03:04')
  })
})

describe('unreadable time strings are returned as written', () => {
  // 오프셋 없는 문자열은 브라우저 시간대로 해석하지 않고 원문을 돌려준다(계약).
  const UNREADABLE = ['', 'abc', '2026-10-23', '2026-10-23T09:30:00', '2026-10-23 09:30', '2026-13-45T99:99:99+09:00']

  // 읽을 수 없는 시각 문자열은 원문 그대로 보인다(formatDateTime).
  // 테스트 코드: TM-040
  it.each(UNREADABLE)('formatDateTime returns %j without throwing', (value) => {
    // when·then: 예외 없이 입력 그대로
    expect(formatDateTime(value)).toBe(value)
  })

  // 읽을 수 없는 시각 문자열은 원문 그대로 보인다(formatStamp).
  // 테스트 코드: TM-040
  it.each(UNREADABLE)('formatStamp returns %j without throwing', (value) => {
    // when·then: 예외 없이 입력 그대로
    expect(formatStamp(value)).toBe(value)
  })
})

describe('date parts written in the string offset', () => {
  // formatDate는 문자열에 적힌 달력 날짜를 보인다.
  // 테스트 코드: TM-039
  it('formatDate keeps the calendar date of the string', () => {
    // when·then: +09:00·-05:00 시각의 날짜 부분
    expect(formatDate('2026-10-23T00:30:00+09:00')).toBe('2026-10-23')
    expect(formatDate('2026-10-23T23:30:00-05:00')).toBe('2026-10-23')
  })

  // 30일 이상 지난 상대 시각은 문자열에 적힌 날짜를 보인다.
  // 테스트 코드: TM-041
  it('formatRelativeTime shows the string date after 30 days', () => {
    // when·then: 30일 이상 전 시각
    expect(formatRelativeTime('2026-08-01T00:30:00+09:00', '2026-10-23T09:30:00+09:00')).toBe('2026-08-01')
    expect(formatRelativeTime('2026-08-01T23:30:00-05:00', '2026-10-23T09:30:00+09:00')).toBe('2026-08-01')
  })
})
