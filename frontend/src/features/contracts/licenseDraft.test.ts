import { describe, expect, it } from 'vitest'
import { licenseDays } from './licenseDraft'

describe('licenseDays', () => {
  it.each([
    ['2026-01-31', '2026-03-17', 46],
    ['2024-02-28', '2024-03-01', 3],
    ['2026-03-18', '2026-03-18', 1],
    ['2026-03-18', '2026-03-17', null],
    ['2026-01-31', '', null],
    ['2026-01-31', '2026-02-30', null],
  ])('counts the inclusive period from %s through %s', (start, end, days) => {
    expect(licenseDays(start, end)).toBe(days)
  })
})
