import { describe, expect, it } from 'vitest'
import { DEFAULT_STALE_DAYS } from './constants'
import { computeRisk, isOverdueRow, statusDays } from './risk'

const NOW = '2026-10-15T09:00:00+09:00'
const STALE = 14

describe('computeRisk', () => {
  const base = { statusKey: 'prospecting', forecastKey: 'commit', earliestOpenDue: '2026-10-20', lastUpdatedOn: '2026-10-14' }

  // Due가 오늘이면 기한초과가 아니다.
  // 테스트 코드: RK-066, RK-079
  it('T-RISK-01 Due가 오늘이면 기한초과가 아니다', () => {
    // when: 가장 이른 Open Due가 오늘인 Deal을 판정한다
    const result = computeRisk({ ...base, earliestOpenDue: '2026-10-15' }, NOW, STALE)
    // then: risk가 null이다
    expect(result).toBeNull()
  })

  // Due가 어제면 기한초과다.
  // 테스트 코드: RK-066, RK-079
  it('T-RISK-02 Due가 어제면 기한초과다', () => {
    // when: Due가 어제인 Deal을 판정한다
    const result = computeRisk({ ...base, earliestOpenDue: '2026-10-14' }, NOW, STALE)
    // then: risk가 overdue다
    expect(result).toBe('overdue')
  })

  // 마지막 갱신 14일째는 미업데이트, 13일째는 정상이다.
  // 테스트 코드: RK-066
  it('T-RISK-03 마지막 갱신 14일째는 미업데이트, 13일째는 정상이다', () => {
    // when: 14일 전과 13일 전에 갱신한 Deal을 판정한다
    const result1 = computeRisk({ ...base, lastUpdatedOn: '2026-10-01' }, NOW, STALE)
    const result2 = computeRisk({ ...base, lastUpdatedOn: '2026-10-02' }, NOW, STALE)
    // then: 14일째는 stale, 13일째는 null이다
    expect(result1).toBe('stale')
    expect(result2).toBeNull()
  })

  // 기한초과이면서 미업데이트면 overdue_stale이다.
  // 테스트 코드: RK-066
  it('T-RISK-04 둘 다면 overdue_stale이다', () => {
    // when: Due가 지났고 오래 갱신하지 않은 Deal을 판정한다
    const result = computeRisk({ ...base, earliestOpenDue: '2026-10-01', lastUpdatedOn: '2026-09-20' }, NOW, STALE)
    // then: risk가 overdue_stale이다
    expect(result).toBe(
      'overdue_stale',
    )
  })

  // Won·Lost 종결 Deal은 항상 risk가 없다.
  // 테스트 코드: RK-066
  it('T-RISK-05 Won·Lost 종결 Deal은 항상 risk가 없다', () => {
    // given: Due가 지나고 오래전에 갱신한 상태다
    const stale = { earliestOpenDue: '2026-01-01', lastUpdatedOn: '2026-01-01' }
    // when: Due가 지나고 오래된 Won·Lost Deal을 판정한다
    const result = computeRisk({ ...base, forecastKey: 'won', ...stale }, NOW, STALE)
    // then: 둘 다 null이다
    expect(result).toBeNull()
    expect(computeRisk({ ...base, forecastKey: 'lost', ...stale }, NOW, STALE)).toBeNull()
  })

  it('excludes 계약완료 from stale even when Forecast is still open', () => {
    const completed = { ...base, statusKey: 'contract_completed', lastUpdatedOn: '2026-09-20' }
    expect(computeRisk(completed, NOW, STALE)).toBeNull()
    expect(computeRisk({ ...completed, earliestOpenDue: '2026-10-01' }, NOW, STALE)).toBe('overdue')
  })

  // Action이 없어 Due가 null이면 기한초과가 아니다.
  // 테스트 코드: RK-066, RK-079
  it('Open Next Action이 없어 earliestOpenDue가 null이면 기한초과가 아니다', () => {
    // when: Due가 null인 Deal을 판정한다
    const result = computeRisk({ ...base, earliestOpenDue: null }, NOW, STALE)
    // then: risk가 null이다
    expect(result).toBeNull()
  })

  // 오늘은 now 문자열의 달력 날짜를 쓴다(UTC로 바꾸지 않는다).
  // 테스트 코드: RK-066
  it('오늘은 now 문자열의 달력 날짜를 쓴다(UTC로 바꾸지 않는다)', () => {
    // when: 서울 00:30(UTC로는 전날)에 판정한다
    const result = computeRisk({ ...base, earliestOpenDue: '2026-10-14' }, '2026-10-15T00:30:00+09:00', STALE)
    // then: 서울 달력 날짜로 어제 Due가 기한초과다
    expect(result).toBe('overdue')
  })

  // 주어진 staleDays를 쓴다: 기준 7일이면 7일째는 stale, 6일째는 정상이다.
  // 테스트 코드: RK-066
  it('uses the given staleDays: 7 days is stale at a 7-day threshold, 6 days is not', () => {
    // when: 기준 7일로 7일 전과 6일 전 갱신 Deal을 판정한다
    const result1 = computeRisk({ ...base, lastUpdatedOn: '2026-10-08' }, NOW, 7)
    const result2 = computeRisk({ ...base, lastUpdatedOn: '2026-10-09' }, NOW, 7)
    // then: 7일째는 stale, 6일째는 null이다
    expect(result1).toBe('stale')
    expect(result2).toBeNull()
  })

  // 14일 된 Deal은 기준 30일에서 정상이고 기준 1일에서는 어제 갱신이 stale, 오늘 갱신은 정상이다.
  // 테스트 코드: RK-066
  it('treats a 14-day-old deal as healthy at a 30-day threshold and stale at 1', () => {
    // given: 14일 전에 갱신한 Deal이다
    const old = { ...base, lastUpdatedOn: '2026-10-01' }
    // when: 기준 30일과 1일로 판정한다
    const result = computeRisk(old, NOW, 30)
    // then: 30일에서 null, 1일에서 어제 갱신은 stale, 오늘 갱신은 null이다
    expect(result).toBeNull()
    expect(computeRisk({ ...base, lastUpdatedOn: '2026-10-14' }, NOW, 1)).toBe('stale')
    expect(computeRisk({ ...base, lastUpdatedOn: '2026-10-15' }, NOW, 1)).toBeNull()
  })

  // 기한초과와 사용자 지정 기준을 함께 쓴다.
  // 테스트 코드: RK-066
  it('combines overdue with the custom threshold', () => {
    // given: Due가 지났고 7일 전에 갱신한 Deal이다
    const input = { ...base, earliestOpenDue: '2026-10-01', lastUpdatedOn: '2026-10-08' }
    // when: 기준 7일과 8일로 판정한다
    const result = computeRisk(input, NOW, 7)
    // then: 7일이면 overdue_stale, 8일이면 overdue다
    expect(result).toBe('overdue_stale')
    expect(computeRisk(input, NOW, 8)).toBe('overdue')
  })

  // 종결 Deal은 기준이 얼마든 null이다.
  // 테스트 코드: RK-066
  it('keeps closed deals null whatever the threshold', () => {
    // when: 기준 1일로 오래된 Won Deal을 판정한다
    const result = computeRisk({ ...base, forecastKey: 'won', earliestOpenDue: '2020-01-01', lastUpdatedOn: '2020-01-01' }, NOW, 1)
    // then: risk가 null이다
    expect(result).toBeNull()
  })

  // Fake의 기본 경고 기준은 14다.
  it('keeps the mock default threshold at 14', () => {
    // when: 기본 상수를 읽는다
    const days = DEFAULT_STALE_DAYS
    // then: 14다
    expect(days).toBe(14)
  })
})

describe('statusDays', () => {
  // 진입 당일은 0이고 이후는 달력 날짜 수다.
  // 테스트 코드: RK-066
  it('is 0 on the entry day and counts calendar days after it', () => {
    // when: 당일·어제·5일 전 진입일의 체류 일수를 구한다
    const result1 = statusDays('2026-10-15', NOW)
    const result2 = statusDays('2026-10-14', NOW)
    const result3 = statusDays('2026-10-10', NOW)
    // then: 0, 1, 5다
    expect(result1).toBe(0)
    expect(result2).toBe(1)
    expect(result3).toBe(5)
  })

  // 진입일이 오늘보다 뒤여도 0 아래로 내려가지 않는다.
  // 테스트 코드: RK-066
  it('never goes below 0 when the entry day is after today', () => {
    // when: 미래 진입일의 체류 일수를 구한다
    const result = statusDays('2026-10-20', NOW)
    // then: 0이다
    expect(result).toBe(0)
  })

  // 문자열의 달력 날짜로 세고 UTC로 바꾸지 않는다.
  // 테스트 코드: RK-066
  it('uses the calendar date of the clock string, not UTC', () => {
    // when: UTC로는 이미 다음 날이지만 시계 문자열의 날짜는 10-14인 시각으로 구한다
    const result = statusDays('2026-10-14', '2026-10-14T23:30:00-05:00')
    // then: 진입 당일이라 0이다
    expect(result).toBe(0)
  })
})

describe('isOverdueRow', () => {
  // Open이고 Due가 오늘보다 앞이면 기한초과 행이다.
  it('is overdue when the next action is open and the due date is before today', () => {
    // when: Open이고 Due가 어제인 행을 판정한다
    const result = isOverdueRow('open', '2026-10-14', '2026-10-15')
    // then: true다
    expect(result).toBe(true)
  })

  // Due가 오늘이면 기한초과가 아니다.
  it('is not overdue when the due date is today', () => {
    // when: Open이고 Due가 오늘인 행을 판정한다
    const result = isOverdueRow('open', '2026-10-15', '2026-10-15')
    // then: false다
    expect(result).toBe(false)
  })

  // 종료(수행·미수행) 행은 Due가 지나도 기한초과가 아니다.
  it.each(['done', 'notDone'])('is not overdue when the status is %s', (status) => {
    // when: 종료 상태이고 Due가 지난 행을 판정한다
    const result = isOverdueRow(status, '2026-10-01', '2026-10-15')
    // then: false다
    expect(result).toBe(false)
  })

  // Due가 없거나 상태가 없으면(Next Action 없음) 기한초과가 아니다.
  it('is not overdue without a due date or without a status', () => {
    // when: Due가 null인 행과 상태가 null인 행을 판정한다
    const noDue = isOverdueRow('open', null, '2026-10-15')
    const noStatus = isOverdueRow(null, '2026-10-01', '2026-10-15')
    // then: 둘 다 false다
    expect(noDue).toBe(false)
    expect(noStatus).toBe(false)
  })
})
