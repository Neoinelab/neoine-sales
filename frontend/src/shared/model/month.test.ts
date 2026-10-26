import { describe, expect, it } from 'vitest'
import { monthsOfQuarter } from './month'

describe('monthsOfQuarter', () => {
  it.each([
    [1, [1, 2, 3]],
    [2, [4, 5, 6]],
    [3, [7, 8, 9]],
    [4, [10, 11, 12]],
  ] as const)('returns the three months of quarter %i', (quarter, months) => {
    expect(monthsOfQuarter(quarter)).toEqual(months)
  })
})
