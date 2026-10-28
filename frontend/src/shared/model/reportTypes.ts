import type { UserRef } from './types'

/**
 * Reports(리포트 디자이너) 모델 타입. 서버 계약(`schema.d.ts`의 Report*)을 화면용 camelCase로 옮긴 것이다.
 * 서버 응답 키는 `gateway/http/mappers/report.ts`가 이 모양으로 바꾼다.
 */

export type ReportEntity = 'deal' | 'action'
export type ReportFieldType = 'text' | 'code' | 'user' | 'number' | 'date' | 'datetime'
export type ReportFormat =
  | 'thousands'
  | 'krw_thousand'
  | 'krw_million'
  | 'decimal1'
  | 'percent_share'
  | 'ymd'
  | 'ymd_hm'
  | 'year'
  | 'quarter'
  | 'month'
  | 'weekday'
  | 'relative'
export type ReportOperator =
  | 'contains'
  | 'equals'
  | 'starts_with'
  | 'is_empty'
  | 'is_not_empty'
  | 'in'
  | 'not_in'
  | 'eq'
  | 'ne'
  | 'gt'
  | 'gte'
  | 'lt'
  | 'lte'
  | 'between'
  | 'before'
  | 'after'
  | 'relative'
export type ReportAggregate = 'sum' | 'avg' | 'min' | 'max' | 'count' | 'count_distinct'
export type ReportOperatorShape = 'text' | 'list' | 'number' | 'range' | 'date' | 'relative' | 'none'
export type ReportRelativePeriod = 'this_year' | 'this_quarter' | 'this_month' | 'last_n_days' | 'before_today'
export type ReportValueKind = 'key' | 'id'
export type ReportOptionsSource = 'users' | 'vendors' | 'status_codes' | 'forecast_codes' | 'bant_labels' | 'action_types'
export type ReportValueType = 'text' | 'integer' | 'decimal' | 'date' | 'datetime'
export type ReportCell = string | number | null
export type ReportCombine = 'and' | 'or'
export type ReportSortDirection = 'asc' | 'desc'

export interface ReportField {
  key: string
  label: string
  entity: ReportEntity
  type: ReportFieldType
  formats: ReportFormat[]
  defaultFormat: ReportFormat | null
  operators: ReportOperator[]
  aggregates: ReportAggregate[]
  defaultAggregate: ReportAggregate | null
  groupable: boolean
  filterable: boolean
  requiresGrouping: boolean
  dealNumber: boolean
  valueKind: ReportValueKind | null
  options: { value: string; label: string }[] | null
  optionsSource: ReportOptionsSource | null
  optionsCategory: string | null
}

export interface ReportLimits {
  columnsMin: number
  columnsMax: number
  conditionsMax: number
  rowLimits: number[]
  defaultRowLimit: number
  statementTimeoutSeconds: number
  textValueMax: number
  listValueMax: number
  lastNDaysMax: number
  labelMax: number
  prefixMax: number
}

export interface ReportCatalog {
  limits: ReportLimits
  entities: { key: ReportEntity; label: string }[]
  formats: { key: ReportFormat; label: string; affectsQuery: boolean }[]
  operators: { key: ReportOperator; label: string; shape: ReportOperatorShape }[]
  aggregates: { key: ReportAggregate; label: string }[]
  relativePeriods: { key: ReportRelativePeriod; label: string; needsDays: boolean }[]
  fields: ReportField[]
}

export type ReportConditionValue =
  | string
  | number
  | (string | number)[]
  | [number, number]
  | [string, string]
  | { period: ReportRelativePeriod; days?: number }

export interface ReportColumnInput {
  field: string
  label?: string
  format?: ReportFormat
  prefixLength?: number
  group: boolean
  aggregate?: ReportAggregate
  sort?: ReportSortDirection
}

export interface ReportConditionInput {
  field: string
  operator: ReportOperator
  value?: ReportConditionValue
}

export interface ReportQueryInput {
  columns: ReportColumnInput[]
  conditions: ReportConditionInput[]
  combine: ReportCombine
  rowLimit: number
}

export interface ReportResultColumn {
  index: number
  field: string
  label: string
  entity: ReportEntity
  type: ReportFieldType
  valueType: ReportValueType
  format: ReportFormat | null
  prefixLength: number | null
  group: boolean
  aggregate: ReportAggregate | null
}

export interface ReportResult {
  rowScope: 'deal' | 'action'
  actionFilter: 'none' | 'exists' | 'join'
  dealNumbersOnce: boolean
  columns: ReportResultColumn[]
  rows: ReportCell[][]
  totals: ReportCell[] | null
  totalCount: number
  truncated: boolean
  rowLimit: number
  sql: string
  elapsedMs: number
  today: string
}

/** 서버가 알려 준 정의 위반 한 건. `location`은 서버 요청 본문 기준 위치(예: ['columns', 1, 'aggregate']). */
export interface ReportIssue {
  location: (string | number)[]
  code: string
  message: string
}

export type ReportRunFailure =
  | { kind: 'invalid'; message: string; issues: ReportIssue[] }
  | { kind: 'timeout'; message: string }
  | { kind: 'network'; message: string }
  | { kind: 'other'; message: string }

export type ReportVisibility = 'public' | 'private'

/** 저장된 리포트 목록 한 줄. 결과 데이터는 저장하지 않는다. */
export type ReportChartKind =
  | 'bar'
  | 'horizontal_bar'
  | 'stacked_bar'
  | 'stacked_100_bar'
  | 'line'
  | 'area'
  | 'pie'
  | 'doughnut'
  | 'scatter'
  | 'combo'
export type ReportChartLegend = 'top' | 'right' | 'bottom' | 'none'

/** 저장·요청용 차트 설정. 컬럼은 정의 columns의 index로 가리킨다. */
export interface ReportChartInput {
  kind: ReportChartKind
  category: number | null
  series: number | null
  values: number[]
  swap: boolean
  title: string
  legend: ReportChartLegend
  dataLabels: boolean
  categoryAxisTitle: string
  valueAxisTitle: string
  /** 숫자 칸이 잘못 입력되면 글자 그대로 보내 서버가 위치와 함께 거절한다. */
  valueMin: number | string | null
  valueMax: number | string | null
  secondaryAxis: boolean
}

export interface SavedReportSummary {
  id: number
  name: string
  description: string
  visibility: ReportVisibility
  owner: UserRef
  updatedBy: UserRef
  entities: ReportEntity[]
  createdAt: string
  updatedAt: string
  /** 목록 응답에서는 항상 있다(차트가 없으면 null). 상세(`SavedReport`)는 `chart`로 알 수 있어 채우지 않는다. */
  chartKind?: ReportChartKind | null
}

/** 저장된 리포트 상세: 정의(요청 모양)와 서버가 만든 표시용 SQL, 덮어쓰기 충돌 판정용 revision. */
export interface SavedReport extends SavedReportSummary {
  revision: number
  definition: ReportQueryInput
  generatedSql: string
  chart: ReportChartInput | null
  chartProblem: string | null
}

export interface SavedReportMeta {
  name: string
  description: string
  visibility: ReportVisibility
}

export interface SavedReportInput extends SavedReportMeta {
  definition: ReportQueryInput
  /** null이면 차트 없음. 수정(덮어쓰기)에서 빠뜨리면 서버가 차트를 지우므로 항상 명시한다. */
  chart: ReportChartInput | null
}
