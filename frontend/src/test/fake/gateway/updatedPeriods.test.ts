import { describe, expect, it } from 'vitest'
import { monthsAfter, monthsBefore, updatedPeriods } from './updatedPeriods'

describe('Fake 최종 업데이트 프리셋(서버 규칙과 같은 예)', () => {
  it('같은 날짜의 n개월 전과 2주 전을 오늘 포함으로 돌려준다', () => {
    expect(updatedPeriods('2026-10-21')).toEqual({
      today: '2026-10-21',
      periods: [
        { key: '2w', from: '2026-10-07', to: '2026-10-21' },
        { key: '1m', from: '2026-09-21', to: '2026-10-21' },
        { key: '2m', from: '2026-08-21', to: '2026-10-21' },
        { key: '3m', from: '2026-07-21', to: '2026-10-21' },
        { key: '6m', from: '2026-04-21', to: '2026-10-21' },
      ],
      upcoming: [
        { key: '1m', from: '2026-10-21', to: '2026-11-21' },
        { key: '2m', from: '2026-10-21', to: '2026-12-21' },
      ],
    })
  })

  it.each([
    ['2026-03-31', 1, '2026-02-28'],
    ['2024-03-31', 1, '2024-02-29'],
    ['2026-08-31', 6, '2026-02-28'],
    ['2026-05-31', 3, '2026-02-28'],
    ['2026-12-31', 6, '2026-06-30'],
    ['2026-01-15', 3, '2025-10-15'],
    ['2026-02-10', 6, '2025-08-10'],
  ] as const)('%s의 %i개월 전은 %s', (day, months, expected) => {
    expect(monthsBefore(day, months)).toBe(expected)
  })

  it('2주 전은 달과 해를 넘는다', () => {
    expect(updatedPeriods('2026-01-05').periods[0]).toEqual({ key: '2w', from: '2025-12-22', to: '2026-01-05' })
  })
})

describe('Fake 향후 프리셋(오늘부터 n개월 뒤, 말일 보정)', () => {
  it('resolves upcoming with month-end fallback', () => {
    expect(updatedPeriods('2026-01-31').upcoming).toEqual([
      { key: '1m', from: '2026-01-31', to: '2026-02-28' },
      { key: '2m', from: '2026-01-31', to: '2026-03-31' },
    ])
  })

  it.each([
    ['2026-10-22', 0, '2026-10-22'],
    ['2024-01-31', 1, '2024-02-29'],
    ['2026-12-31', 2, '2027-02-28'],
    ['2026-03-31', 1, '2026-04-30'],
    ['2026-07-31', 2, '2026-09-30'],
    ['2026-11-15', 2, '2027-01-15'],
    ['2024-02-29', 12, '2025-02-28'],
  ] as const)('%s의 %i개월 뒤는 %s', (day, months, expected) => {
    expect(monthsAfter(day, months)).toBe(expected)
  })
})
