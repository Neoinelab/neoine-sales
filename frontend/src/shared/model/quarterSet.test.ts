import { describe, expect, it } from 'vitest'
import { QUARTERS, effectiveQuarters, monthsOfQuarters, parseQuarterParam, quarterParam, quarterSummary, toggleQuarter } from './quarterSet'

describe('QUARTERS', () => {
  it('lists the four quarters in order', () => {
    expect(QUARTERS).toEqual([1, 2, 3, 4])
  })
})

describe('parseQuarterParam (URL 분기 값 → 오름차순·중복 제거)', () => {
  it.each([null, ''])('reads %j as no quarter', (raw) => {
    expect(parseQuarterParam(raw)).toEqual([])
  })

  it('reads one quarter', () => {
    expect(parseQuarterParam('2')).toEqual([2])
  })

  it('sorts ascending and drops duplicates', () => {
    expect(parseQuarterParam('3,1,1')).toEqual([1, 3])
  })

  it('drops items in the wrong format and keeps the valid ones', () => {
    expect(parseQuarterParam(' 1 , 5,x,4')).toEqual([1, 4])
  })

  it.each(['0', '5', '-1', '1.5', 'abc', '01', ',', ' '])('drops the whole value %j when no item is valid', (raw) => {
    expect(parseQuarterParam(raw)).toEqual([])
  })

  it('keeps all four quarters as they are (the screen shows what the user pressed)', () => {
    expect(parseQuarterParam('1,2,3,4')).toEqual([1, 2, 3, 4])
    expect(parseQuarterParam('4,3,2,1')).toEqual([1, 2, 3, 4])
  })
})

describe('quarterParam', () => {
  it('writes an ascending comma list', () => {
    expect(quarterParam([3, 1])).toBe('1,3')
  })

  it('writes an empty string for no quarter', () => {
    expect(quarterParam([])).toBe('')
  })

  it('drops duplicates', () => {
    expect(quarterParam([2, 2, 4])).toBe('2,4')
  })

  it('writes all four quarters as they are', () => {
    expect(quarterParam([4, 3, 2, 1])).toBe('1,2,3,4')
  })
})

describe('toggleQuarter', () => {
  it('turns a quarter on and keeps the list ascending', () => {
    expect(toggleQuarter([1], 3, true)).toEqual([1, 3])
    expect(toggleQuarter([3], 1, true)).toEqual([1, 3])
  })

  it('turns a quarter off', () => {
    expect(toggleQuarter([1, 3], 1, false)).toEqual([3])
  })

  it('can turn the last quarter off, leaving none', () => {
    expect(toggleQuarter([2], 2, false)).toEqual([])
  })

  it('does not change anything when a quarter that is on is turned on again', () => {
    expect(toggleQuarter([1, 3], 3, true)).toEqual([1, 3])
  })

  it('does not change anything when a quarter that is off is turned off again', () => {
    expect(toggleQuarter([1, 3], 2, false)).toEqual([1, 3])
  })

  it('does not mutate the list it is given', () => {
    const quarters = [1] as const
    toggleQuarter(quarters, 2, true)

    expect(quarters).toEqual([1])
  })

  it('keeps all four when the fourth is turned on (no normalization here)', () => {
    expect(toggleQuarter([1, 2, 3], 4, true)).toEqual([1, 2, 3, 4])
  })
})

describe('effectiveQuarters (조회·Drill-down용: 없음 = 넷 다 = 전체)', () => {
  it('treats no quarter as no condition', () => {
    expect(effectiveQuarters([])).toEqual([])
  })

  it('treats all four quarters as no condition', () => {
    expect(effectiveQuarters([1, 2, 3, 4])).toEqual([])
    expect(effectiveQuarters([4, 3, 2, 1])).toEqual([])
  })

  it('keeps one to three quarters ascending', () => {
    expect(effectiveQuarters([3, 1])).toEqual([1, 3])
    expect(effectiveQuarters([2])).toEqual([2])
    expect(effectiveQuarters([1, 2, 4])).toEqual([1, 2, 4])
  })
})

describe('quarterSummary', () => {
  it('says 전체 for no quarter and for all four', () => {
    expect(quarterSummary([])).toBe('전체')
    expect(quarterSummary([1, 2, 3, 4])).toBe('전체')
  })

  it('lists the chosen quarters ascending', () => {
    expect(quarterSummary([3, 1])).toBe('Q1, Q3')
    expect(quarterSummary([4])).toBe('Q4')
  })
})

describe('monthsOfQuarters (월 선택지)', () => {
  it('offers the twelve months for no quarter and for all four', () => {
    expect(monthsOfQuarters([])).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    expect(monthsOfQuarters([1, 2, 3, 4])).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
  })

  it('offers the union of the months of the chosen quarters ascending', () => {
    expect(monthsOfQuarters([1, 3])).toEqual([1, 2, 3, 7, 8, 9])
    expect(monthsOfQuarters([3, 1])).toEqual([1, 2, 3, 7, 8, 9])
  })

  it('offers the three months of one quarter', () => {
    expect(monthsOfQuarters([4])).toEqual([10, 11, 12])
  })
})
