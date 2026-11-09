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
    // given: 오늘 2027-03-15
    // when: 발급(신규·갱신) 계약의 만료 단계를 구한다
    // then: 경계 날짜에서 위험·주의·없음이 기대와 같다
    expect(expiryLevel(end, 'issued_new', today)).toBe(level)
    expect(expiryLevel(end, 'issued_renewal', today)).toBe(level)
  })

  // 종료일이 이미 지난 발급 계약은 위험이다.
  // 테스트 코드: LC-027
  it('treats an already ended issued contract as danger', () => {
    // given: 오늘 2027-03-15
    // when: 지난 종료일의 만료 단계를 구한다
    // then: danger다
    expect(expiryLevel('2027-02-28', 'issued_new', today)).toBe('danger')
    expect(expiryLevel('2027-02-28', 'issued_renewal', today)).toBe('danger')
  })

  // 종료·미발급 계약은 종료일이 가까워도 단계가 없다.
  // 테스트 코드: LC-027
  it('has no level for ended or not-issued contracts, even with a near end date', () => {
    // given: 오늘 2027-03-15
    // when: 종료·미발급 상태의 만료 단계를 구한다
    // then: null이다
    expect(expiryLevel('2027-03-31', 'ended', today)).toBeNull()
    expect(expiryLevel('2027-03-31', 'not_issued', today)).toBeNull()
  })

  // 종료일이 없으면 단계가 없다.
  // 테스트 코드: LC-027
  it('has no level without an end date', () => {
    // given: 오늘 2027-03-15
    // when: 종료일 없는 발급 계약의 만료 단계를 구한다
    // then: null이다
    expect(expiryLevel(null, 'issued_renewal', today)).toBeNull()
  })

  // 오늘+N개월은 같은 날이 없으면 그 달 말일로 계산한다.
  // 테스트 코드: LC-027
  it('clamps today + N months to the last day of a short month', () => {
    // 2027-01-31 + 1개월 = 2027-02-28, + 2개월 = 2027-03-31
    // given: 오늘 2027-01-31
    // when: 경계 종료일의 만료 단계를 구한다
    // then: 2월 28일·3월 31일 기준으로 단계가 갈린다
    expect(expiryLevel('2027-02-27', 'issued_new', '2027-01-31')).toBe('danger')
    expect(expiryLevel('2027-02-28', 'issued_new', '2027-01-31')).toBe('warning')
    expect(expiryLevel('2027-03-30', 'issued_new', '2027-01-31')).toBe('warning')
    expect(expiryLevel('2027-03-31', 'issued_new', '2027-01-31')).toBeNull()
  })
})
