import { describe, expect, it } from 'vitest'
import { isCartesianKind } from './build/cartesian'
import { CHART_FAMILIES, CHART_KINDS, CHART_POINTS_MAX, CHART_VALUES_MAX, kindLabel, kindRule } from './chartKinds'

/**
 * 종류별 규칙표(명세 RC-R2, 33종). backend `KIND_RULES`와 같은 표이며 서버가 정본이다(차이는 저장 때 422로 드러난다).
 * 열: [key, 화면 이름, 분류 key, 최대 그룹핑 수, 최소 그룹핑 수, 계열 가능, 값 최소, 값 최대, 행/열 전환, 축 범위, 보조 축, 0~100 축, 범주 사용, 옵션]
 * 옵션은 서버 `ChartOption` 값(`histogram`·`show_total`·`combo_series`)이다.
 */
type Row = readonly [string, string, string, number, number, boolean, number, number, boolean, boolean, boolean, boolean, boolean, readonly string[]]

const none: readonly string[] = []
const cartesian = (key: string, label: string, family: string, percent = false): Row => [key, label, family, 2, 1, true, 1, 10, true, true, false, percent, true, none]
const xy = (key: string, label: string): Row => [key, label, 'xy', 1, 1, false, 2, 10, false, true, false, false, true, none]
const radar = (key: string, label: string): Row => [key, label, 'radar', 2, 1, true, 1, 10, true, true, false, false, true, none]

const TABLE: readonly Row[] = [
  cartesian('bar', '묶은 세로 막대', 'column'),
  cartesian('stacked_bar', '누적 세로 막대', 'column'),
  cartesian('stacked_100_bar', '100% 누적 세로 막대', 'column', true),
  cartesian('horizontal_bar', '묶은 가로 막대', 'bar'),
  cartesian('stacked_horizontal_bar', '누적 가로 막대', 'bar'),
  cartesian('stacked_100_horizontal_bar', '100% 누적 가로 막대', 'bar', true),
  cartesian('line', '꺾은선', 'line'),
  cartesian('line_markers', '표식이 있는 꺾은선', 'line'),
  cartesian('stacked_line', '누적 꺾은선', 'line'),
  cartesian('stacked_line_markers', '표식이 있는 누적 꺾은선', 'line'),
  cartesian('stacked_100_line', '100% 누적 꺾은선', 'line', true),
  cartesian('stacked_100_line_markers', '표식이 있는 100% 누적 꺾은선', 'line', true),
  ['pie', '원형', 'pie', 1, 1, false, 1, 1, false, false, false, false, true, none],
  ['doughnut', '도넛형', 'pie', 1, 1, false, 1, 1, false, false, false, false, true, none],
  cartesian('area', '영역', 'area'),
  cartesian('stacked_area', '누적 영역', 'area'),
  cartesian('stacked_100_area', '100% 누적 영역', 'area', true),
  xy('scatter', '분산형(표식만)'),
  xy('scatter_smooth_markers', '곡선 및 표식이 있는 분산형'),
  xy('scatter_smooth', '곡선이 있는 분산형'),
  xy('scatter_line_markers', '직선 및 표식이 있는 분산형'),
  xy('scatter_line', '직선이 있는 분산형'),
  ['bubble', '거품형', 'xy', 1, 1, false, 3, 3, false, true, false, false, true, none],
  radar('radar', '방사형'),
  radar('radar_markers', '표식이 있는 방사형'),
  radar('radar_filled', '채워진 방사형'),
  ['treemap', '트리맵', 'treemap', 2, 1, true, 1, 1, false, false, false, false, true, none],
  ['sunburst', '선버스트', 'sunburst', 2, 1, true, 1, 1, false, false, false, false, true, none],
  ['histogram', '히스토그램', 'histogram', 2, 0, false, 1, 1, false, true, false, false, false, ['histogram']],
  ['pareto', '파레토', 'histogram', 1, 1, false, 1, 1, false, true, false, false, true, none],
  ['waterfall', '폭포', 'waterfall', 1, 1, false, 1, 1, false, true, false, false, true, ['show_total']],
  ['funnel', '깔때기', 'funnel', 1, 1, false, 1, 1, false, false, false, false, true, none],
  ['combo', '콤보', 'combo', 1, 1, false, 2, 10, false, true, true, false, true, ['combo_series']],
]

const FAMILIES = [
  ['column', '세로 막대형'],
  ['bar', '가로 막대형'],
  ['line', '꺾은선형'],
  ['pie', '원형'],
  ['area', '영역형'],
  ['xy', '분산형(X, Y) 또는 거품형'],
  ['radar', '방사형'],
  ['treemap', '트리맵'],
  ['sunburst', '선버스트'],
  ['histogram', '히스토그램'],
  ['waterfall', '폭포'],
  ['funnel', '깔때기'],
  ['combo', '콤보'],
] as const

describe('차트 종류 규칙표', () => {
  // 테스트 코드: RC-049
  it('종류는 33개이고 키가 규칙표와 같다', () => {
    // when: 종류 목록을 읽는다
    const actual = new Set(CHART_KINDS.map((k) => k.key)).size
    const actual2 = CHART_KINDS.map((k) => k.key).sort()
    // then: 33개이고 키가 중복 없이 규칙표 키와 같다
    expect(CHART_KINDS).toHaveLength(33)
    expect(actual).toBe(33)
    expect(actual2).toEqual(TABLE.map((row) => row[0]).sort())
  })

  // 테스트 코드: RC-049
  it.each(TABLE.map((row): [string, Row] => [row[0], row]))(
    '종류마다 화면 이름·분류·규칙이 규칙표와 같다 (%s)',
    (_name, row) => {
      // given: 종류 하나의 기대 규칙 행
      const [key, label, family, maxGroups, minGroups, allowsSeries, valuesMin, valuesMax, allowsSwap, allowsValueRange, allowsSecondary, percentAxis, usesCategory, options] = row
      // when: 규칙표에서 종류를 찾는다
      const kind = CHART_KINDS.find((k) => k.key === key)

      // then: 이름·분류·그룹 수·값 개수·전환·범위·보조 축·옵션이 기대 행과 같다
      expect(kind).toMatchObject({ key, label, family, maxGroups, minGroups, allowsSeries, valuesMin, valuesMax, allowsSwap, allowsValueRange, allowsSecondary, percentAxis, usesCategory })
      expect([...(kind?.options ?? [])].sort()).toEqual([...options].sort())
    },
  )

  // 테스트 코드: RC-049
  it('분류 13개가 Excel 대화상자 순서다', () => {
    // when: 분류 목록을 읽는다
    const actual = CHART_FAMILIES.map((f) => [f.key, f.label])
    // then: 13개가 키·이름·순서까지 기대와 같다
    expect(actual).toEqual(FAMILIES)
  })

  // 테스트 코드: RC-049
  it('모든 종류는 알려진 분류에 속한다', () => {
    // given: 분류 키 집합
    const keys = new Set(CHART_FAMILIES.map((f) => f.key))

    // when: 모든 종류의 분류가 분류 목록에 있는지 확인한다
    const actual = CHART_KINDS.every((k) => keys.has(k.family))
    // then: 모든 종류의 분류가 그 집합에 있다
    expect(actual).toBe(true)
  })

  // 테스트 코드: RC-049
  it('분류별 하위 종류 수가 명세와 같다 (3·3·6·2·3·6·3·1·1·2·1·1·1)', () => {
    // when: 분류별 하위 종류 수를 센다
    const counts = Object.fromEntries(CHART_FAMILIES.map((f) => [f.key, CHART_KINDS.filter((k) => k.family === f.key).length]))

    // then: 집계한 수가 명세 표와 같다
    expect(counts).toEqual({ column: 3, bar: 3, line: 6, pie: 2, area: 3, xy: 6, radar: 3, treemap: 1, sunburst: 1, histogram: 2, waterfall: 1, funnel: 1, combo: 1 })
  })

  // 테스트 코드: RC-049
  it('종류 키로 규칙과 화면 이름을 찾는다', () => {
    // when: 100% 누적 가로 막대의 퍼센트 축 여부와 채워진 방사형의 이름을 구한다
    const actual = kindRule('stacked_100_horizontal_bar').percentAxis
    const actual2 = kindLabel('radar_filled')
    // then: 100% 누적 가로 막대는 퍼센트 축이고 채워진 방사형의 이름은 '채워진 방사형'이다
    expect(actual).toBe(true)
    expect(actual2).toBe('채워진 방사형')
  })

  // 테스트 코드: RC-049
  it('그룹 0개와 범주 없음을 허용하는 종류는 히스토그램뿐이다', () => {
    // when: 그룹이 없어도 되는 종류와 범주를 쓰지 않는 종류를 거른다
    const actual = CHART_KINDS.filter((k) => k.minGroups === 0).map((k) => k.key)
    const actual2 = CHART_KINDS.filter((k) => !k.usesCategory).map((k) => k.key)
    // then: 둘 다 히스토그램 하나뿐이다
    expect(actual).toEqual(['histogram'])
    expect(actual2).toEqual(['histogram'])
  })

  // 테스트 코드: RC-049
  it('값은 최대 10개, 점은 최대 1,000개 한도다', () => {
    // when: 한도 상수를 읽는다
    const limits = { values: CHART_VALUES_MAX, points: CHART_POINTS_MAX }
    // then: 값 10개, 점 1,000개다
    expect(limits).toEqual({ values: 10, points: 1000 })
  })
})

/** 서버 `ChartKind`와 같은 33개 키(명시 목록). */
const EXPECTED_KEYS = ['bar', 'stacked_bar', 'stacked_100_bar', 'horizontal_bar', 'stacked_horizontal_bar', 'stacked_100_horizontal_bar', 'line', 'line_markers', 'stacked_line', 'stacked_line_markers', 'stacked_100_line', 'stacked_100_line_markers', 'pie', 'doughnut', 'area', 'stacked_area', 'stacked_100_area', 'scatter', 'scatter_smooth_markers', 'scatter_smooth', 'scatter_line_markers', 'scatter_line', 'bubble', 'radar', 'radar_markers', 'radar_filled', 'treemap', 'sunburst', 'histogram', 'pareto', 'waterfall', 'funnel', 'combo']

/** 막대·꺾은선·영역 빌더 판정은 규칙표 분류(column·bar·line·area)와 일치한다. */
describe('막대·꺾은선·영역 종류 판정', () => {
  // 테스트 코드: RC-049
  it('규칙표의 키가 서버 종류와 같은 33개다', () => {
    // when: 규칙표 키를 정렬한다
    const actual = CHART_KINDS.map((k) => k.key).sort()
    // then: 서버 종류 33개 목록과 같다
    expect(actual).toEqual([...EXPECTED_KEYS].sort())
  })

  // 테스트 코드: RC-049
  it.each(EXPECTED_KEYS)('종류가 막대·꺾은선·영역 계열인지는 분류(세로·가로 막대·꺾은선·영역)로 판정한다 (%s)', (kind) => {
    // given: 종류의 분류
    const family = CHART_KINDS.find((k) => k.key === kind)?.family
    // when: 각 종류가 직교 좌표 종류인지 판정한다
    const actual = isCartesianKind(kind as Parameters<typeof isCartesianKind>[0])
    // then: 막대·꺾은선·영역 판정이 분류와 일치한다
    expect(actual).toBe(['column', 'bar', 'line', 'area'].includes(family ?? ''))
  })
})
