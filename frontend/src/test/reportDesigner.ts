/** Reports 디자이너 테스트 공용 도구(운영 코드에서 쓰지 않는다): 카탈로그 조회, 리듀서 연속 적용, 결과·열 빌더. */

import {
  designerReducer,
  initialDesignerState,
  type DesignerAction,
  type DesignerColumn,
  type DesignerState,
} from '../features/reports/designer/state/designerState'
import type { ReportCell, ReportField, ReportResult, ReportResultColumn } from '../shared/model/reportTypes'
import { REPORT_CATALOG } from './fake/seed/reportCatalog'

export { REPORT_CATALOG }

export function fieldOf(key: string): ReportField {
  const found = REPORT_CATALOG.fields.find((f) => f.key === key)
  if (!found) throw new Error(`카탈로그에 없는 필드: ${key}`)
  return found
}

export function emptyDesign(): DesignerState {
  return initialDesignerState(REPORT_CATALOG.limits)
}

/** 액션을 차례로 적용한다. */
export function reduce(state: DesignerState, ...actions: DesignerAction[]): DesignerState {
  return actions.reduce((current, action) => designerReducer(current, action, REPORT_CATALOG), state)
}

/** 필드 key들을 컬럼으로 차례로 추가한 설계. */
export function withColumns(...keys: string[]): DesignerState {
  return reduce(emptyDesign(), ...keys.map((key): DesignerAction => ({ type: 'addColumn', field: fieldOf(key) })))
}

/** 설계에서 i번째 컬럼. */
export function columnAt(state: DesignerState, index: number): DesignerColumn {
  const column = state.columns[index]
  if (!column) throw new Error(`${index}번째 컬럼 없음`)
  return column
}

export function uidAt(state: DesignerState, index: number): number {
  return columnAt(state, index).uid
}

export function conditionUidAt(state: DesignerState, index: number): number {
  const condition = state.conditions[index]
  if (!condition) throw new Error(`${index}번째 조건 없음`)
  return condition.uid
}

export function resultColumn(over: Partial<ReportResultColumn> = {}): ReportResultColumn {
  return {
    index: 0,
    field: 'deal.code',
    label: 'Deal code',
    entity: 'deal',
    type: 'text',
    valueType: 'text',
    format: null,
    unit: null,
    prefixLength: null,
    group: false,
    aggregate: null,
    ...over,
  }
}

/** 결과 한 건. 열 정의에 맞게 rows를 주면 된다. */
export function resultOf(over: Partial<ReportResult> = {}): ReportResult {
  const columns = over.columns ?? [resultColumn()]
  return {
    rowScope: 'deal',
    actionFilter: 'none',
    dealNumbersOnce: false,
    columns,
    rows: [['20261016-0001']],
    totals: null,
    totalCount: over.rows?.length ?? 1,
    truncated: false,
    rowLimit: 1000,
    sql: 'SELECT demo',
    elapsedMs: 210,
    today: '2026-10-15',
    ...over,
  }
}

/** Vendor별 금액 합계(그룹 1 + 합계 1) 결과. 합계 행 확인용. */
export function groupedAmountResult(rows: ReportCell[][], totals: ReportCell[] | null): ReportResult {
  return resultOf({
    columns: [
      resultColumn({ index: 0, field: 'deal.vendor', label: 'Vendor', type: 'code', format: null, group: true }),
      resultColumn({ index: 1, field: 'deal.amount', label: '금액 합계', type: 'number', valueType: 'integer', format: null, unit: 'krw_thousand', aggregate: 'sum' }),
    ],
    rows,
    totals,
    totalCount: rows.length,
  })
}
