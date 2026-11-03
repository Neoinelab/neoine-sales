import { describe, expect, it } from 'vitest'
import type { ReportHistogramBins } from '../../../../shared/model/reportTypes'
import { histogramBins } from './histogramBins'

/**
 * `histogramBins(values, bins, formatNumber?)`: 표본 값 → 구간별 개수(Excel 확장 AC10).
 * 반환 `Bin[]` = `{ label, count, kind: 'underflow' | 'range' | 'overflow' }`, 순서는 언더플로 → 구간들 → 오버플로.
 * 빈 값(null)은 제외한다. 구간 이름의 숫자는 `formatNumber`(기본 `String`)로 쓴다.
 */

const auto = (over: Partial<ReportHistogramBins> = {}): ReportHistogramBins => ({ binMode: 'auto', binCount: null, binWidth: null, overflow: null, underflow: null, ...over })
const TEN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
const ZERO_TO_TEN = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
const counts = (values: (number | null)[], bins: ReportHistogramBins) => histogramBins(values, bins).map((b) => b.count)
const labels = (values: (number | null)[], bins: ReportHistogramBins) => histogramBins(values, bins).map((b) => b.label)

describe('histogramBins: auto (Scott rule)', () => {
  it('makes two bins for 1..10 (width 3.49*s*n^(-1/3) = 4.9, ceil(9 / 4.9) = 2)', () => {
    const result = histogramBins(TEN, auto())

    expect(result).toHaveLength(2)
    expect(result.map((b) => b.count)).toEqual([5, 5])
    expect(result.every((b) => b.kind === 'range')).toBe(true)
  })

  it('keeps every value: the counts add up to the sample size', () => {
    const values = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

    expect(counts(values, auto()).reduce((a, b) => a + b, 0)).toBe(values.length)
  })

  it.each([
    ['one value', [5]],
    ['all values equal', [5, 5, 5, 5]],
  ])('makes a single bin [min, max] for %s', (_name, values) => {
    const result = histogramBins(values, auto())

    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ label: '[5, 5]', count: values.length })
  })

  it('caps the number of bins at 100', () => {
    const values = Array.from({ length: 5000 }, (_, i) => (i % 2 === 0 ? i : i * 1000))

    expect(histogramBins(values, auto()).length).toBeLessThanOrEqual(100)
  })

  it('ignores empty values and returns no bins for an empty sample', () => {
    expect(counts([null, 1, 2, null], auto()).reduce((a, b) => a + b, 0)).toBe(2)
    expect(histogramBins([], auto())).toEqual([])
    expect(histogramBins([null, null], auto())).toEqual([])
  })
})

describe('histogramBins: count mode', () => {
  it('splits the range into equal bins and closes only the first one on the left', () => {
    const bins = auto({ binMode: 'count', binCount: 5 })

    expect(labels(ZERO_TO_TEN, bins)).toEqual(['[0, 2]', '(2, 4]', '(4, 6]', '(6, 8]', '(8, 10]'])
    expect(counts(ZERO_TO_TEN, bins)).toEqual([3, 2, 2, 2, 2])
  })

  it('puts a value on a boundary into the lower bin', () => {
    const bins = auto({ binMode: 'count', binCount: 2 })

    expect(counts([0, 5, 10], bins)).toEqual([2, 1]) // 5는 [0, 5]에 든다
  })

  it('makes one bin for a count of 1', () => {
    expect(histogramBins(ZERO_TO_TEN, auto({ binMode: 'count', binCount: 1 }))).toMatchObject([{ label: '[0, 10]', count: 11 }])
  })

  it('makes exactly 100 bins for a count of 100', () => {
    expect(histogramBins(ZERO_TO_TEN, auto({ binMode: 'count', binCount: 100 }))).toHaveLength(100)
  })
})

describe('histogramBins: width mode', () => {
  it('starts at the minimum and steps by the width', () => {
    const bins = auto({ binMode: 'width', binWidth: 5 })

    expect(labels(ZERO_TO_TEN, bins)).toEqual(['[0, 5]', '(5, 10]'])
    expect(counts(ZERO_TO_TEN, bins)).toEqual([6, 5])
  })

  it('lets the last bin run past the maximum when the width does not divide the range', () => {
    const bins = auto({ binMode: 'width', binWidth: 4 })

    expect(labels(ZERO_TO_TEN, bins)).toEqual(['[0, 4]', '(4, 8]', '(8, 12]'])
    expect(counts(ZERO_TO_TEN, bins)).toEqual([5, 4, 2])
  })
})

describe('histogramBins: overflow and underflow', () => {
  const bins = auto({ binMode: 'count', binCount: 3, overflow: 8, underflow: 2 })

  it('puts the values beyond the limits into their own bins at both ends', () => {
    const result = histogramBins(TEN, bins)

    expect(result.map((b) => b.kind)).toEqual(['underflow', 'range', 'range', 'range', 'overflow'])
    expect(result[0]).toMatchObject({ label: '≤ 2', count: 2 })
    expect(result.at(-1)).toMatchObject({ label: '> 8', count: 2 })
  })

  it('splits only the values between the limits into the regular bins', () => {
    const inner = histogramBins(TEN, bins).filter((b) => b.kind === 'range')

    expect(inner.map((b) => b.count)).toEqual([2, 2, 2])
  })

  it('supports only an overflow bin', () => {
    const result = histogramBins(TEN, auto({ binMode: 'count', binCount: 2, overflow: 8 }))

    expect(result.at(-1)).toMatchObject({ label: '> 8', count: 2, kind: 'overflow' })
    expect(result.some((b) => b.kind === 'underflow')).toBe(false)
  })

  it('supports only an underflow bin', () => {
    const result = histogramBins(TEN, auto({ binMode: 'count', binCount: 2, underflow: 2 }))

    expect(result[0]).toMatchObject({ label: '≤ 2', count: 2, kind: 'underflow' })
    expect(result.some((b) => b.kind === 'overflow')).toBe(false)
  })
})

describe('histogramBins: bin names', () => {
  it('writes the numbers with the given formatter', () => {
    const result = histogramBins(ZERO_TO_TEN, auto({ binMode: 'count', binCount: 2 }), (n) => `${n * 1000}원`)

    expect(result.map((b) => b.label)).toEqual(['[0원, 5000원]', '(5000원, 10000원]'])
  })
})
