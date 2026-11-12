import { describe, expect, it } from 'vitest'
import { expiryLevel } from './contractExpiry'

describe('expiryLevel (B8)', () => {
  const today = '2027-03-15'

  // 발급 계약은 종료일이 오늘+1개월 미만이면 위험, +2개월 미만이면 주의다.
  // 테스트 코드: LC-027
  it.each([
    ['2027-03-15', 'danger'],
    ['2027-03-31', 'danger'],
    ['2027-04-14', 'danger'],
    ['2027-04-15', 'warning'],
    ['2027-05-14', 'warning'],
    ['2027-05-15', null],
    ['2028-01-01', null],
  ] as const)('issued contract ending %s is %s for both issued statuses (C7)', (end, level) => {
    // when: 발급(신규·갱신) 계약의 만료 단계를 구한다 (전제: 오늘 2027-03-15)
    const result = expiryLevel(end, 'issued_new', today)
    // then: 경계 날짜에서 위험·주의·없음이 기대와 같다
    expect(result).toBe(level)
    expect(expiryLevel(end, 'issued_renewal', today)).toBe(level)
  })

  // 종료일이 이미 지난 발급 계약은 위험이다.
  // 테스트 코드: LC-027
  it('treats an already ended issued contract as danger', () => {
    // when: 지난 종료일의 만료 단계를 구한다 (전제: 오늘 2027-03-15)
    const result1 = expiryLevel('2027-02-28', 'issued_new', today)
    const result2 = expiryLevel('2027-02-28', 'issued_renewal', today)
    // then: danger다
    expect(result1).toBe('danger')
    expect(result2).toBe('danger')
  })

  // 종료·미발급 계약은 종료일이 가까워도 단계가 없다.
  // 테스트 코드: LC-027
  it('has no level for ended or not-issued contracts, even with a near end date', () => {
    // when: 종료·미발급 상태의 만료 단계를 구한다 (전제: 오늘 2027-03-15)
    const result1 = expiryLevel('2027-03-31', 'ended', today)
    const result2 = expiryLevel('2027-03-31', 'not_issued', today)
    // then: null이다
    expect(result1).toBeNull()
    expect(result2).toBeNull()
  })

  // 종료일이 없으면 단계가 없다.
  // 테스트 코드: LC-027
  it('has no level without an end date', () => {
    // when: 종료일 없는 발급 계약의 만료 단계를 구한다 (전제: 오늘 2027-03-15)
    const result = expiryLevel(null, 'issued_renewal', today)
    // then: null이다
    expect(result).toBeNull()
  })

  // 오늘+N개월은 같은 날이 없으면 그 달 말일로 계산한다.
  // 테스트 코드: LC-027
  it('clamps today + N months to the last day of a short month', () => {
    // 2027-01-31 + 1개월 = 2027-02-28, + 2개월 = 2027-03-31
    // when: 경계 종료일의 만료 단계를 구한다 (전제: 오늘 2027-01-31)
    const result1 = expiryLevel('2027-02-27', 'issued_new', '2027-01-31')
    const result2 = expiryLevel('2027-02-28', 'issued_new', '2027-01-31')
    const result3 = expiryLevel('2027-03-30', 'issued_new', '2027-01-31')
    const result4 = expiryLevel('2027-03-31', 'issued_new', '2027-01-31')
    // then: 2월 28일·3월 31일 기준으로 단계가 갈린다
    expect(result1).toBe('danger')
    expect(result2).toBe('warning')
    expect(result3).toBe('warning')
    expect(result4).toBeNull()
  })
})
