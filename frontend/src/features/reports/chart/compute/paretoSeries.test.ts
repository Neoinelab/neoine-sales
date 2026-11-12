import { describe, expect, it } from 'vitest'
import { paretoSeries } from './paretoSeries'

/**
 * `paretoSeries(labels, values)` (명세 RC-R53): 0 이하·빈 값 항목을 빼고 값 내림차순(같으면 결과 순서 유지)으로 정렬한다.
 * 반환 `{ labels, values, cumulative, skipped }`. `cumulative`는 누계 / 합계 × 100(%), `skipped`는 뺀 항목 수.
 */

describe('paretoSeries: 파레토 계열 계산', () => {
  // 테스트 코드: RC-101
  it('입력 순서와 상관없이 값 내림차순으로 정렬한다', () => {
    // when: 값 [10, 60, 30]으로 파레토 계열을 구한다
    const result = paretoSeries(['A', 'B', 'C'], [10, 60, 30])

    // then: 이름과 값이 B, C, A / 60, 30, 10이다
    expect(result.labels).toEqual(['B', 'C', 'A'])
    expect(result.values).toEqual([60, 30, 10])
  })

  // 테스트 코드: RC-101
  it('값이 같으면 입력 순서를 유지한다', () => {
    // when: 같은 값이 섞인 입력으로 파레토 계열을 구한다
    const result = paretoSeries(['A', 'B', 'C', 'D'], [5, 9, 5, 5])

    // then: 이름 순서가 B, A, C, D이다
    expect(result.labels).toEqual(['B', 'A', 'C', 'D'])
  })

  // 테스트 코드: RC-101
  it('누계 비율은 퍼센트이고 마지막은 정확히 100이다', () => {
    // when: 값 [10, 60, 30]으로 파레토 계열을 구한다
    const result = paretoSeries(['A', 'B', 'C'], [10, 60, 30])

    // then: 누계가 60, 90, 100이고 마지막이 100이다
    expect(result.cumulative).toEqual([60, 90, 100])
    expect(result.cumulative.at(-1)).toBe(100)
  })

  // 테스트 코드: RC-101
  it('0 이하·빈 값은 빼고 개수를 센다', () => {
    // when: 0·음수·빈 값이 섞인 입력으로 파레토 계열을 구한다
    const result = paretoSeries(['A', 'B', 'C', 'D', 'E'], [10, 0, -5, null, 30])

    // then: 남은 항목이 E, A이고 누계 75, 100, 뺀 개수 3이다
    expect(result.labels).toEqual(['E', 'A'])
    expect(result.cumulative).toEqual([75, 100])
    expect(result.skipped).toBe(3)
  })

  // 테스트 코드: RC-101
  it('모두 계산에 들어가면 뺀 개수가 0이다', () => {
    // when: 값 하나로 파레토 계열을 구한다
    const actual = paretoSeries(['A'], [3]).skipped

    // then: 뺀 개수가 0이다
    expect(actual).toBe(0)
  })

  // 테스트 코드: RC-101
  it('양수가 없으면 빈 계열이다', () => {
    // when: 양수가 없는 입력으로 파레토 계열을 구한다
    const actual = paretoSeries(['A', 'B'], [0, null])

    // then: 이름·값·누계가 비고 뺀 개수가 2다
    expect(actual).toMatchObject({ labels: [], values: [], cumulative: [], skipped: 2 })
  })
})
