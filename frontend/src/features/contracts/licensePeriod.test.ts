import { describe, expect, it } from 'vitest'
import { licenseEnd } from './licensePeriod'

describe('licenseEnd (B4)', () => {
  // 종료일은 시작일 + 기간 - 1일이다(말일 보정 포함).
  // 테스트 코드: LC-040
  it.each([
    ['2026-01-01', 1, 'year', '2026-12-31'],
    ['2026-01-01', 6, 'month', '2026-06-30'],
    ['2026-01-01', 12, 'month', '2026-12-31'],
    ['2026-01-01', 2, 'year', '2027-12-31'],
    ['2026-03-15', 1, 'month', '2026-04-14'],
    ['2026-07-01', 1, 'month', '2026-07-31'],
    ['2026-12-01', 1, 'month', '2026-12-31'],
    ['2026-11-15', 3, 'month', '2027-02-14'],
    ['2027-12-31', 2, 'month', '2028-02-29'],
    ['2028-01-30', 1, 'month', '2028-02-29'],
  ] as const)('%s + %i %s ends on %s', (start, amount, unit, expected) => {
    // when: 시작일과 기간으로 종료일을 계산한다
    // then: 기대 종료일과 같다
    expect(licenseEnd(start, amount, unit)).toBe(expected)
  })

  // 짧은 달이면 그 달 말일로 보정한다.
  // 테스트 코드: LC-040
  it('corrects to the last day of a short month (2026-01-31 + 1개월 = 2026-02-28)', () => {
    // when: 2026-01-31 + 1개월을 계산한다
    // then: 2026-02-28이다
    expect(licenseEnd('2026-01-31', 1, 'month')).toBe('2026-02-28')
  })
})
