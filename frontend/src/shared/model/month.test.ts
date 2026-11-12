import { describe, expect, it } from 'vitest'
import { monthsOfQuarter } from './month'

describe('monthsOfQuarter', () => {
  it.each([
    [1, [1, 2, 3]],
    [2, [4, 5, 6]],
    [3, [7, 8, 9]],
    [4, [10, 11, 12]],
  ] as const)('분기 %i의 석 달을 돌려준다', (quarter, months) => {
    // when: 분기의 월 목록을 구한다
    const actual = monthsOfQuarter(quarter)
    // then: 분기에 속한 석 달이 순서대로 나온다
    expect(actual).toEqual(months)
  })
})
