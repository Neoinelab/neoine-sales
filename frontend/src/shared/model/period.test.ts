import { describe, expect, it } from 'vitest'
import { addDays, daysBetween } from './dates'
import { inPeriod, periodOf, userLabel } from './period'

describe('periodOf / inPeriod', () => {
  it('T-FC-01 분기 경계(12/31, 1/1)', () => {
    expect(periodOf('2026-12-31')).toEqual({ year: 2026, quarter: 4 })
    expect(periodOf('2027-01-01')).toEqual({ year: 2027, quarter: 1 })
    expect(periodOf('2026-03-31')).toEqual({ year: 2026, quarter: 1 })
    expect(periodOf('2026-04-01')).toEqual({ year: 2026, quarter: 2 })
    expect(periodOf('2026-06-30').quarter).toBe(2)
    expect(periodOf('2026-07-01').quarter).toBe(3)
    expect(periodOf('2026-09-30').quarter).toBe(3)
    expect(periodOf('2026-10-01').quarter).toBe(4)
  })

  it('inPeriod는 연도와 분기를 함께 본다', () => {
    expect(inPeriod('2026-12-31', 2026)).toBe(true)
    expect(inPeriod('2026-12-31', 2026, 4)).toBe(true)
    expect(inPeriod('2026-12-31', 2026, 3)).toBe(false)
    expect(inPeriod('2027-01-01', 2026)).toBe(false)
    expect(inPeriod('2027-01-01', 2027, 1)).toBe(true)
  })
})

describe('userLabel', () => {
  it('퇴사자는 이름(퇴사)', () => {
    expect(userLabel({ name: '강퇴사', status: 'resigned' })).toBe('강퇴사(퇴사)')
    expect(userLabel({ name: '김영업', status: 'active' })).toBe('김영업')
  })
})

describe('dates', () => {
  it('addDays / daysBetween은 월·연 경계를 처리한다', () => {
    expect(addDays('2026-10-15', 20)).toBe('2026-11-04')
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31')
    expect(daysBetween('2026-10-15', '2026-10-01')).toBe(14)
    expect(daysBetween('2026-10-01', '2026-10-15')).toBe(-14)
  })
})
