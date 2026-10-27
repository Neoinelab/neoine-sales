import { describe, expect, it } from 'vitest'
import { CHART_KINDS, CHART_POINTS_MAX, CHART_VALUES_MAX } from './chartKinds'

/**
 * 종류별 규칙표(계획 4.3). backend `KIND_RULES`와 같은 표이며 서버가 정본이다(차이는 저장 때 422로 드러난다).
 * 열: [key, 화면 이름, 최대 그룹핑 컬럼 수, 계열 가능, 값 최소, 값 최대, 행/열 전환, 축 범위, 보조 축, 0~100 축]
 */
const TABLE = [
  ['bar', '세로 막대', 2, true, 1, 10, true, true, false, false],
  ['horizontal_bar', '가로 막대', 2, true, 1, 10, true, true, false, false],
  ['stacked_bar', '누적 막대', 2, true, 1, 10, true, true, false, false],
  ['stacked_100_bar', '100% 누적', 2, true, 1, 10, true, true, false, true],
  ['line', '꺾은선', 2, true, 1, 10, true, true, false, false],
  ['area', '영역', 2, true, 1, 10, true, true, false, false],
  ['pie', '원', 1, false, 1, 1, false, false, false, false],
  ['doughnut', '도넛', 1, false, 1, 1, false, false, false, false],
  ['scatter', '분산형', 1, false, 2, 2, false, true, false, false],
  ['combo', '콤보', 1, false, 2, 10, false, true, true, false],
] as const

describe('chart kind rules (AC13)', () => {
  it('lists the ten kinds in the order of the design', () => {
    expect(CHART_KINDS.map((k) => k.key)).toEqual(TABLE.map((row) => row[0]))
  })

  it.each(TABLE)('defines %s with its label and rules', (key, label, maxGroups, allowsSeries, valuesMin, valuesMax, allowsSwap, allowsValueRange, allowsSecondary, percentAxis) => {
    const kind = CHART_KINDS.find((k) => k.key === key)

    expect(kind).toMatchObject({ key, label, maxGroups, allowsSeries, valuesMin, valuesMax, allowsSwap, allowsValueRange, allowsSecondary, percentAxis })
  })

  it('limits values to ten (the number of series colors) and points to one thousand', () => {
    expect(CHART_VALUES_MAX).toBe(10)
    expect(CHART_POINTS_MAX).toBe(1000)
  })
})
