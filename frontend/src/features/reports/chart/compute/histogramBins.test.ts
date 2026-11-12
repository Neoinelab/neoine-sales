import { describe, expect, it } from 'vitest'
import type { ReportHistogramBins } from '../../../../shared/model/reportTypes'
import { histogramBins } from './histogramBins'

/**
 * `histogramBins(values, bins, formatNumber?)`: 표본 값 → 구간별 개수(명세 RC-R52).
 * 반환 `Bin[]` = `{ label, count, kind: 'underflow' | 'range' | 'overflow' }`, 순서는 언더플로 → 구간들 → 오버플로.
 * 빈 값(null)은 제외한다. 구간 이름의 숫자는 `formatNumber`(기본 `String`)로 쓴다.
 */

const auto = (over: Partial<ReportHistogramBins> = {}): ReportHistogramBins => ({ binMode: 'auto', binCount: null, binWidth: null, overflow: null, underflow: null, ...over })
const TEN = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
const ZERO_TO_TEN = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
const counts = (values: (number | null)[], bins: ReportHistogramBins) => histogramBins(values, bins).map((b) => b.count)
const labels = (values: (number | null)[], bins: ReportHistogramBins) => histogramBins(values, bins).map((b) => b.label)

describe('histogramBins: 자동(Scott 규칙)', () => {
  // 테스트 코드: RC-099
  it('자동 구간은 1~10을 구간 두 개로 나눈다 (너비 4.9, 올림 2)', () => {
    // when: 값 1~10으로 자동 구간을 구한다
    const result = histogramBins(TEN, auto())

    // then: 구간 2개, 개수 5·5, 모두 일반 구간이다
    expect(result).toHaveLength(2)
    expect(result.map((b) => b.count)).toEqual([5, 5])
    expect(result.every((b) => b.kind === 'range')).toBe(true)
  })

  // 테스트 코드: RC-099
  it('자동 구간도 값을 빠뜨리지 않아 개수의 합이 표본 크기다', () => {
    // given: 표본 12개
    const values = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]

    // when: 자동 구간별 개수를 구한다
    const actual = counts(values, auto()).reduce((a, b) => a + b, 0)

    // then: 개수의 합이 표본 크기와 같다
    expect(actual).toBe(values.length)
  })

  // 테스트 코드: RC-099
  it.each([
    ['one value', [5]],
    ['all values equal', [5, 5, 5, 5]],
  ])('값이 하나이거나 모두 같으면 [최소, 최대] 구간 하나다 (%s)', (_name, values) => {
    // when: 값 하나 또는 같은 값으로 자동 구간을 구한다
    const result = histogramBins(values, auto())

    // then: 구간 하나이고 이름이 [5, 5]이며 개수가 표본 크기다
    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({ label: '[5, 5]', count: values.length })
  })

  // 테스트 코드: RC-099
  it('자동 구간 수는 100개를 넘지 않는다', () => {
    // given: 아주 넓게 퍼진 표본 5,000개
    const values = Array.from({ length: 5000 }, (_, i) => (i % 2 === 0 ? i : i * 1000))

    // when: 자동 구간을 구한다
    const actual = histogramBins(values, auto()).length

    // then: 구간이 100개 이하다
    expect(actual).toBeLessThanOrEqual(100)
  })

  // 테스트 코드: RC-099
  it('빈 값은 제외하고 표본이 비면 구간이 없다', () => {
    // when: null이 섞인 값과 빈 값으로 구간을 계산한다
    const actual = counts([null, 1, 2, null], auto()).reduce((a, b) => a + b, 0)
    const actual2 = histogramBins([], auto())
    const actual3 = histogramBins([null, null], auto())
    // then: 빈 값 섞인 표본은 값만 세고, 빈 표본이나 빈 값뿐인 표본은 구간이 없다
    expect(actual).toBe(2)
    expect(actual2).toEqual([])
    expect(actual3).toEqual([])
  })
})

describe('histogramBins: 구간 수 방식', () => {
  // 테스트 코드: RC-099
  it('구간 수 방식은 범위를 같은 너비로 나누고 첫 구간만 왼쪽을 닫는다', () => {
    // given: 구간 수 5 설정
    const bins = auto({ binMode: 'count', binCount: 5 })

    // when: 0~10 값을 주어진 구간으로 나눠 이름과 개수를 구한다
    const actual = labels(ZERO_TO_TEN, bins)
    const actual2 = counts(ZERO_TO_TEN, bins)
    // then: 구간 이름이 [0, 2], (2, 4]…이고 개수가 3·2·2·2·2다
    expect(actual).toEqual(['[0, 2]', '(2, 4]', '(4, 6]', '(6, 8]', '(8, 10]'])
    expect(actual2).toEqual([3, 2, 2, 2, 2])
  })

  // 테스트 코드: RC-099
  it('경계에 놓인 값은 아래 구간에 든다', () => {
    // given: 구간 수 2 설정
    const bins = auto({ binMode: 'count', binCount: 2 })

    // when: 0, 5, 10의 개수를 구한다
    const actual = counts([0, 5, 10], bins)

    // then: 5는 [0, 5]에 들어 2·1이다
    expect(actual).toEqual([2, 1]) // 5는 [0, 5]에 든다
  })

  // 테스트 코드: RC-099
  it('구간 수가 1이면 구간 하나다', () => {
    // when: 구간 수 1로 구간을 구한다
    const actual = histogramBins(ZERO_TO_TEN, auto({ binMode: 'count', binCount: 1 }))

    // then: [0, 10] 구간 하나에 11개다
    expect(actual).toMatchObject([{ label: '[0, 10]', count: 11 }])
  })

  // 테스트 코드: RC-099
  it('구간 수가 100이면 정확히 100개 구간이다', () => {
    // when: 구간 수 100으로 구간을 구한다
    const actual = histogramBins(ZERO_TO_TEN, auto({ binMode: 'count', binCount: 100 }))

    // then: 구간이 100개다
    expect(actual).toHaveLength(100)
  })
})

describe('histogramBins: 구간 너비 방식', () => {
  // 테스트 코드: RC-099
  it('구간 너비 방식은 최소에서 시작해 너비만큼 나아간다', () => {
    // given: 구간 너비 5 설정
    const bins = auto({ binMode: 'width', binWidth: 5 })

    // when: 0~10 값을 주어진 구간으로 나눠 이름과 개수를 구한다
    const actual = labels(ZERO_TO_TEN, bins)
    const actual2 = counts(ZERO_TO_TEN, bins)
    // then: 구간 이름이 [0, 5], (5, 10]이고 개수가 6·5다
    expect(actual).toEqual(['[0, 5]', '(5, 10]'])
    expect(actual2).toEqual([6, 5])
  })

  // 테스트 코드: RC-099
  it('너비가 범위를 나누어 떨어지지 않으면 마지막 구간이 최대를 넘어간다', () => {
    // given: 구간 너비 4 설정
    const bins = auto({ binMode: 'width', binWidth: 4 })

    // when: 0~10 값을 주어진 구간으로 나눠 이름과 개수를 구한다
    const actual = labels(ZERO_TO_TEN, bins)
    const actual2 = counts(ZERO_TO_TEN, bins)
    // then: 구간 이름이 [0, 4], (4, 8], (8, 12]이고 개수가 5·4·2다
    expect(actual).toEqual(['[0, 4]', '(4, 8]', '(8, 12]'])
    expect(actual2).toEqual([5, 4, 2])
  })
})

describe('histogramBins: 오버플로·언더플로', () => {
  const bins = auto({ binMode: 'count', binCount: 3, overflow: 8, underflow: 2 })

  // 테스트 코드: RC-100
  it('한도 밖의 값은 양끝에 따로 센다', () => {
    // when: 구간 수 3에 오버플로 8·언더플로 2를 줘서 구간을 구한다 (전제: 값 1~10)
    const result = histogramBins(TEN, bins)

    // then: 언더플로, 일반 구간 3개, 오버플로 순서이고 "≤ 2"와 "> 8"이 각각 2개다
    expect(result.map((b) => b.kind)).toEqual(['underflow', 'range', 'range', 'range', 'overflow'])
    expect(result[0]).toMatchObject({ label: '≤ 2', count: 2 })
    expect(result.at(-1)).toMatchObject({ label: '> 8', count: 2 })
  })

  // 테스트 코드: RC-100
  it('일반 구간에는 한도 사이의 값만 나눈다', () => {
    // when: 같은 설정으로 일반 구간만 모은다
    const inner = histogramBins(TEN, bins).filter((b) => b.kind === 'range')

    // then: 일반 구간 개수가 2·2·2다
    expect(inner.map((b) => b.count)).toEqual([2, 2, 2])
  })

  // 테스트 코드: RC-100
  it('오버플로 구간만 둘 수 있다', () => {
    // when: 오버플로만 줘서 구간을 구한다
    const result = histogramBins(TEN, auto({ binMode: 'count', binCount: 2, overflow: 8 }))

    // then: 마지막이 "> 8" 오버플로이고 언더플로는 없다
    expect(result.at(-1)).toMatchObject({ label: '> 8', count: 2, kind: 'overflow' })
    expect(result.some((b) => b.kind === 'underflow')).toBe(false)
  })

  // 테스트 코드: RC-100
  it('언더플로 구간만 둘 수 있다', () => {
    // when: 언더플로만 줘서 구간을 구한다
    const result = histogramBins(TEN, auto({ binMode: 'count', binCount: 2, underflow: 2 }))

    // then: 처음이 "≤ 2" 언더플로이고 오버플로는 없다
    expect(result[0]).toMatchObject({ label: '≤ 2', count: 2, kind: 'underflow' })
    expect(result.some((b) => b.kind === 'overflow')).toBe(false)
  })
})

describe('histogramBins: 구간 이름', () => {
  // 테스트 코드: RC-100
  it('구간 이름의 숫자는 주어진 서식으로 쓴다', () => {
    // when: 원 단위 서식 함수를 줘서 구간을 구한다
    const result = histogramBins(ZERO_TO_TEN, auto({ binMode: 'count', binCount: 2 }), (n) => `${n * 1000}원`)

    // then: 구간 이름이 서식대로 [0원, 5000원], (5000원, 10000원]이다
    expect(result.map((b) => b.label)).toEqual(['[0원, 5000원]', '(5000원, 10000원]'])
  })
})
