import { describe, expect, it } from 'vitest'
import { paretoSeries } from './paretoSeries'

/**
 * `paretoSeries(labels, values)` (Excel 확장 AC11): 0 이하·빈 값 항목을 빼고 값 내림차순(같으면 결과 순서 유지)으로 정렬한다.
 * 반환 `{ labels, values, cumulative, skipped }`. `cumulative`는 누계 / 합계 × 100(%), `skipped`는 뺀 항목 수.
 */

describe('paretoSeries', () => {
  it('sorts the bars by value descending regardless of the input order', () => {
    const result = paretoSeries(['A', 'B', 'C'], [10, 60, 30])

    expect(result.labels).toEqual(['B', 'C', 'A'])
    expect(result.values).toEqual([60, 30, 10])
  })

  it('keeps the input order for equal values', () => {
    const result = paretoSeries(['A', 'B', 'C', 'D'], [5, 9, 5, 5])

    expect(result.labels).toEqual(['B', 'A', 'C', 'D'])
  })

  it('accumulates the share in percent and ends at exactly 100', () => {
    const result = paretoSeries(['A', 'B', 'C'], [10, 60, 30])

    expect(result.cumulative).toEqual([60, 90, 100])
    expect(result.cumulative.at(-1)).toBe(100)
  })

  it('leaves out values of zero or less and empty values and counts them', () => {
    const result = paretoSeries(['A', 'B', 'C', 'D', 'E'], [10, 0, -5, null, 30])

    expect(result.labels).toEqual(['E', 'A'])
    expect(result.cumulative).toEqual([75, 100])
    expect(result.skipped).toBe(3)
  })

  it('reports nothing skipped when every value counts', () => {
    expect(paretoSeries(['A'], [3]).skipped).toBe(0)
  })

  it('returns empty series when nothing is positive', () => {
    expect(paretoSeries(['A', 'B'], [0, null])).toMatchObject({ labels: [], values: [], cumulative: [], skipped: 2 })
  })
})
