import type { ReportChartKind } from '../../../shared/model/reportTypes'

/** 값 열은 최대 10개(색 10개와 같다). */
export const CHART_VALUES_MAX = 10
/** 범주 수 × 데이터셋 수가 이보다 많으면 그리지 않는다. */
export const CHART_POINTS_MAX = 1000

/** 분류(Excel "차트 삽입" 대화상자의 왼쪽 목록) 13개. 순서가 화면 순서다. */
export const CHART_FAMILIES = [
  { key: 'column', label: '세로 막대형' },
  { key: 'bar', label: '가로 막대형' },
  { key: 'line', label: '꺾은선형' },
  { key: 'pie', label: '원형' },
  { key: 'area', label: '영역형' },
  { key: 'xy', label: '분산형(X, Y) 또는 거품형' },
  { key: 'radar', label: '방사형' },
  { key: 'treemap', label: '트리맵' },
  { key: 'sunburst', label: '선버스트' },
  { key: 'histogram', label: '히스토그램' },
  { key: 'waterfall', label: '폭포' },
  { key: 'funnel', label: '깔때기' },
  { key: 'combo', label: '콤보' },
] as const

export type ChartFamilyKey = (typeof CHART_FAMILIES)[number]['key']

/** 종류가 쓰는 옵션(서버 `ChartOption` 값). */
export type ChartOptionKey = 'histogram' | 'show_total' | 'combo_series'

/** 종류별 규칙. backend `KIND_RULES`와 같은 표이며 서버가 정본이다(차이는 저장 때 422로 드러난다). */
export interface ChartKindRule {
  key: ReportChartKind
  label: string
  family: ChartFamilyKey
  /** 쓸 수 있는 그룹핑 컬럼 수의 최대/최소. */
  maxGroups: 1 | 2
  minGroups: 0 | 1
  allowsSeries: boolean
  valuesMin: number
  valuesMax: number
  allowsSwap: boolean
  allowsValueRange: boolean
  allowsSecondary: boolean
  /** 100% 누적: 값 축이 0~100. */
  percentAxis: boolean
  /** 범주 열을 쓰는지(히스토그램만 쓰지 않는다). */
  usesCategory: boolean
  options: readonly ChartOptionKey[]
}

type Spec = Pick<ChartKindRule, 'key' | 'label' | 'family'> & Partial<ChartKindRule>

const base = {
  maxGroups: 1,
  minGroups: 1,
  allowsSeries: false,
  valuesMin: 1,
  valuesMax: 1,
  allowsSwap: false,
  allowsValueRange: true,
  allowsSecondary: false,
  percentAxis: false,
  usesCategory: true,
  options: [],
} as const satisfies Omit<ChartKindRule, 'key' | 'label' | 'family'>

const multi = { maxGroups: 2, allowsSeries: true, valuesMax: CHART_VALUES_MAX, allowsSwap: true } as const
const xy = { valuesMin: 2, valuesMax: CHART_VALUES_MAX } as const
const single = { allowsValueRange: false } as const

const rule = (spec: Spec): ChartKindRule => ({ ...base, ...spec })

export const CHART_KINDS: readonly ChartKindRule[] = [
  rule({ key: 'bar', label: '묶은 세로 막대', family: 'column', ...multi }),
  rule({ key: 'stacked_bar', label: '누적 세로 막대', family: 'column', ...multi }),
  rule({ key: 'stacked_100_bar', label: '100% 누적 세로 막대', family: 'column', ...multi, percentAxis: true }),
  rule({ key: 'horizontal_bar', label: '묶은 가로 막대', family: 'bar', ...multi }),
  rule({ key: 'stacked_horizontal_bar', label: '누적 가로 막대', family: 'bar', ...multi }),
  rule({ key: 'stacked_100_horizontal_bar', label: '100% 누적 가로 막대', family: 'bar', ...multi, percentAxis: true }),
  rule({ key: 'line', label: '꺾은선', family: 'line', ...multi }),
  rule({ key: 'line_markers', label: '표식이 있는 꺾은선', family: 'line', ...multi }),
  rule({ key: 'stacked_line', label: '누적 꺾은선', family: 'line', ...multi }),
  rule({ key: 'stacked_line_markers', label: '표식이 있는 누적 꺾은선', family: 'line', ...multi }),
  rule({ key: 'stacked_100_line', label: '100% 누적 꺾은선', family: 'line', ...multi, percentAxis: true }),
  rule({ key: 'stacked_100_line_markers', label: '표식이 있는 100% 누적 꺾은선', family: 'line', ...multi, percentAxis: true }),
  rule({ key: 'pie', label: '원형', family: 'pie', ...single }),
  rule({ key: 'doughnut', label: '도넛형', family: 'pie', ...single }),
  rule({ key: 'area', label: '영역', family: 'area', ...multi }),
  rule({ key: 'stacked_area', label: '누적 영역', family: 'area', ...multi }),
  rule({ key: 'stacked_100_area', label: '100% 누적 영역', family: 'area', ...multi, percentAxis: true }),
  rule({ key: 'scatter', label: '분산형(표식만)', family: 'xy', ...xy }),
  rule({ key: 'scatter_smooth_markers', label: '곡선 및 표식이 있는 분산형', family: 'xy', ...xy }),
  rule({ key: 'scatter_smooth', label: '곡선이 있는 분산형', family: 'xy', ...xy }),
  rule({ key: 'scatter_line_markers', label: '직선 및 표식이 있는 분산형', family: 'xy', ...xy }),
  rule({ key: 'scatter_line', label: '직선이 있는 분산형', family: 'xy', ...xy }),
  rule({ key: 'bubble', label: '거품형', family: 'xy', valuesMin: 3, valuesMax: 3 }),
  rule({ key: 'radar', label: '방사형', family: 'radar', ...multi }),
  rule({ key: 'radar_markers', label: '표식이 있는 방사형', family: 'radar', ...multi }),
  rule({ key: 'radar_filled', label: '채워진 방사형', family: 'radar', ...multi }),
  rule({ key: 'treemap', label: '트리맵', family: 'treemap', maxGroups: 2, allowsSeries: true, ...single }),
  rule({ key: 'sunburst', label: '선버스트', family: 'sunburst', maxGroups: 2, allowsSeries: true, ...single }),
  rule({ key: 'histogram', label: '히스토그램', family: 'histogram', maxGroups: 2, minGroups: 0, usesCategory: false, options: ['histogram'] }),
  rule({ key: 'pareto', label: '파레토', family: 'histogram' }),
  rule({ key: 'waterfall', label: '폭포', family: 'waterfall', options: ['show_total'] }),
  rule({ key: 'funnel', label: '깔때기', family: 'funnel', ...single }),
  rule({ key: 'combo', label: '콤보', family: 'combo', valuesMin: 2, valuesMax: CHART_VALUES_MAX, allowsSecondary: true, options: ['combo_series'] }),
]

export function kindRule(kind: ReportChartKind): ChartKindRule {
  return CHART_KINDS.find((k) => k.key === kind) ?? CHART_KINDS[0]!
}

export const kindLabel = (kind: ReportChartKind): string => kindRule(kind).label
