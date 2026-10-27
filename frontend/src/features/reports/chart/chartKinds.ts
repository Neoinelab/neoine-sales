import type { ReportChartKind } from '../../../shared/model/reportTypes'

/** 값 열은 최대 10개(색 10개와 같다). */
export const CHART_VALUES_MAX = 10
/** 범주 수 × 데이터셋 수가 이보다 많으면 그리지 않는다. */
export const CHART_POINTS_MAX = 1000

/** 종류별 규칙. backend `KIND_RULES`와 같은 표이며 서버가 정본이다(차이는 저장 때 422로 드러난다). */
export interface ChartKindRule {
  key: ReportChartKind
  label: string
  /** 쓸 수 있는 그룹핑 컬럼 수의 최대. */
  maxGroups: 1 | 2
  allowsSeries: boolean
  valuesMin: number
  valuesMax: number
  allowsSwap: boolean
  allowsValueRange: boolean
  allowsSecondary: boolean
  /** 100% 누적: 값 축이 0~100. */
  percentAxis: boolean
}

const multi = { maxGroups: 2, allowsSeries: true, valuesMin: 1, valuesMax: CHART_VALUES_MAX, allowsSwap: true, allowsValueRange: true, allowsSecondary: false, percentAxis: false } as const
const single = { maxGroups: 1, allowsSeries: false, allowsSwap: false, allowsSecondary: false, percentAxis: false } as const

export const CHART_KINDS: readonly ChartKindRule[] = [
  { key: 'bar', label: '세로 막대', ...multi },
  { key: 'horizontal_bar', label: '가로 막대', ...multi },
  { key: 'stacked_bar', label: '누적 막대', ...multi },
  { key: 'stacked_100_bar', label: '100% 누적', ...multi, percentAxis: true },
  { key: 'line', label: '꺾은선', ...multi },
  { key: 'area', label: '영역', ...multi },
  { key: 'pie', label: '원', ...single, valuesMin: 1, valuesMax: 1, allowsValueRange: false },
  { key: 'doughnut', label: '도넛', ...single, valuesMin: 1, valuesMax: 1, allowsValueRange: false },
  { key: 'scatter', label: '분산형', ...single, valuesMin: 2, valuesMax: 2, allowsValueRange: true },
  { key: 'combo', label: '콤보', ...single, valuesMin: 2, valuesMax: CHART_VALUES_MAX, allowsValueRange: true, allowsSecondary: true },
]

export function kindRule(kind: ReportChartKind): ChartKindRule {
  return CHART_KINDS.find((k) => k.key === kind) ?? CHART_KINDS[0]!
}

export const kindLabel = (kind: ReportChartKind): string => kindRule(kind).label
