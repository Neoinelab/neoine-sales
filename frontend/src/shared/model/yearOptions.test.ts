import { describe, expect, it } from 'vitest'
import { selectableYears } from './yearOptions'

/** 연도 선택지 규칙(R2): min(earliest, 올해) ~ 올해+1 연속(오름차순) + 범위 밖 URL 연도(있으면). Deals 목록·Dashboard·Forecast 공통. */

const range = (from: number, to: number): number[] => Array.from({ length: to - from + 1 }, (_, i) => from + i)

describe('selectableYears', () => {
  it('builds every year from the earliest to next year', () => {
    expect(selectableYears(2026, 2023)).toEqual([2023, 2024, 2025, 2026, 2027])
  })

  it('lists the years without data too (no gaps)', () => {
    expect(selectableYears(2026, 2019)).toEqual(range(2019, 2027))
  })

  it('keeps this and next year when there is no data', () => {
    expect(selectableYears(2026, null)).toEqual([2026, 2027])
  })

  it('keeps this and next year while the earliest year is not known yet', () => {
    expect(selectableYears(2026, undefined)).toEqual([2026, 2027])
  })

  it('starts at this year when the earliest year is this year', () => {
    expect(selectableYears(2026, 2026)).toEqual([2026, 2027])
  })

  it('starts at this year when the earliest year is in the future', () => {
    expect(selectableYears(2026, 2027)).toEqual([2026, 2027])
  })

  it('ignores data years after next year', () => {
    expect(selectableYears(2026, 2029)).toEqual([2026, 2027])
  })

  it('has no this year + 2 any more', () => {
    expect(selectableYears(2026, 2023)).not.toContain(2028)
  })

  it('adds an out-of-range current year after the range, once', () => {
    expect(selectableYears(2026, 2023, 2030)).toEqual([2023, 2024, 2025, 2026, 2027, 2030])
  })

  it('adds an out-of-range current year before the range in order', () => {
    expect(selectableYears(2026, 2023, 2015)).toEqual([2015, 2023, 2024, 2025, 2026, 2027])
  })

  it('does not duplicate a current year that is already offered', () => {
    expect(selectableYears(2026, 2023, 2024)).toEqual([2023, 2024, 2025, 2026, 2027])
  })

  it('adds the current year when the earliest year is unknown', () => {
    expect(selectableYears(2026, null, 2024)).toEqual([2024, 2026, 2027])
  })

  it('is always ascending and unique', () => {
    const years = selectableYears(2026, 2000, 1990)
    expect(years).toEqual([...new Set(years)].sort((a, b) => a - b))
  })

  it('moves with this year', () => {
    expect(selectableYears(2027, 2025)).toEqual([2025, 2026, 2027, 2028])
  })
})
