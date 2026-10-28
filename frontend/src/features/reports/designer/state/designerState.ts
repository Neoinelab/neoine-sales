import type {
  ReportAggregate,
  ReportCatalog,
  ReportCombine,
  ReportField,
  ReportFormat,
  ReportLimits,
  ReportOperator,
  ReportSortDirection,
} from '../../../../shared/model/reportTypes'
import { normalizeForKind, reconcileChart, type ChartDraft } from '../../chart/chartDraft'
import { fieldByKey } from './columnRules'
import { emptyDraft, type ConditionDraft } from './conditionDraft'

export type { ConditionDraft } from './conditionDraft'

/** 앞 N자 보기를 켤 때의 N 기본값. */
const DEFAULT_PREFIX_LENGTH = 20

export interface DesignerColumn {
  uid: number
  field: string
  /** 비면(공백 제외) 요청에서 생략하고 필드 이름을 쓴다. */
  label: string
  /** 포맷이 없는 필드(텍스트·코드·사용자)는 null. */
  format: ReportFormat | null
  /** 앞 N자만 보기(표시 전용, 서버는 N만 저장). */
  prefixOn: boolean
  prefixLength: number | null
  group: boolean
  aggregate: ReportAggregate | null
  /** 정렬 방향(없으면 정렬하지 않음). 우선순위는 컬럼 순서(왼쪽 먼저)다. */
  sort: ReportSortDirection | null
}

export interface DesignerCondition {
  uid: number
  field: string
  operator: ReportOperator
  draft: ConditionDraft
}

export interface DesignerState {
  columns: DesignerColumn[]
  conditions: DesignerCondition[]
  combine: ReportCombine
  rowLimit: number
  /** 차트 초안(저장·되돌리기 대상이지만 조회 결과를 낡게 하지 않는다). */
  chart: ChartDraft | null
  selectedUid: number | null
  /** 다음에 발급할 uid. 한 번 쓴 uid는 다시 쓰지 않는다. */
  nextUid: number
}

export type DesignerAction =
  | { type: 'addColumn'; field: ReportField }
  | { type: 'removeColumn'; uid: number }
  | { type: 'moveColumn'; uid: number; to: number }
  | { type: 'selectColumn'; uid: number | null }
  | { type: 'updateColumn'; uid: number; patch: Partial<Omit<DesignerColumn, 'uid' | 'field'>> }
  | { type: 'addCondition'; field: ReportField }
  | { type: 'changeConditionField'; uid: number; field: ReportField }
  | { type: 'changeOperator'; uid: number; operator: ReportOperator }
  | { type: 'changeDraft'; uid: number; draft: ConditionDraft }
  | { type: 'removeCondition'; uid: number }
  | { type: 'setCombine'; combine: ReportCombine }
  | { type: 'setRowLimit'; rowLimit: number }
  | { type: 'createChart'; chart: ChartDraft }
  | { type: 'changeChart'; patch: Partial<ChartDraft> }
  | { type: 'setChartKind'; kind: ChartDraft['kind'] }
  | { type: 'removeChart' }
  | { type: 'reset' }
  /** 저장된 설계로 통째로 바꾼다(되돌리기). uid는 되돌아가지 않게 nextUid를 이어 간다. */
  | { type: 'load'; state: DesignerState }

export function initialDesignerState(limits: ReportLimits): DesignerState {
  return { columns: [], conditions: [], combine: 'and', rowLimit: limits.defaultRowLimit, chart: null, selectedUid: null, nextUid: 1 }
}

/** 초기 상태와 내용이 다르면 true(uid·선택은 보지 않는다). 컬럼을 넣었다 빼면 다시 false다. */
export function isDirty(state: DesignerState, limits: ReportLimits): boolean {
  return (
    state.columns.length > 0 ||
    state.conditions.length > 0 ||
    state.combine !== 'and' ||
    state.rowLimit !== limits.defaultRowLimit ||
    state.chart !== null
  )
}

const sameValue = (a: unknown, b: unknown): boolean => a === b || JSON.stringify(a) === JSON.stringify(b)

/** 컬럼·조건·결합·정렬·최대 행이 같은 내용인지(선택·차트 변경은 조회가 달라지는 설계 변경이 아니다). */
export function sameDesign(a: DesignerState, b: DesignerState): boolean {
  return (
    sameValue(a.columns, b.columns) && sameValue(a.conditions, b.conditions) && a.combine === b.combine && a.rowLimit === b.rowLimit
  )
}

const hasGroup = (columns: readonly DesignerColumn[]): boolean => columns.some((c) => c.group)

/**
 * 그룹 컬럼 유무가 바뀐 뒤 집계를 맞춘다. 그룹이 없으면 모든 집계를 비우고,
 * 그룹이 있으면 집계가 비어 있는 비그룹 컬럼에 필드의 기본 집계를 채운다(숫자 합계·평균, Action 건수. 텍스트는 비워 둔다).
 */
function reconcileAggregates(columns: DesignerColumn[], catalog: ReportCatalog): DesignerColumn[] {
  const grouped = hasGroup(columns)
  return columns.map((column) => {
    if (column.group || !grouped) return column.aggregate === null ? column : { ...column, aggregate: null }
    if (column.aggregate !== null) return column
    const fallback = fieldByKey(catalog, column.field)?.defaultAggregate ?? null
    return fallback === null ? column : { ...column, aggregate: fallback }
  })
}

function newColumn(uid: number, field: ReportField, grouped: boolean): DesignerColumn {
  return {
    uid,
    field: field.key,
    label: '',
    format: field.defaultFormat,
    prefixOn: false,
    prefixLength: null,
    group: false,
    aggregate: grouped ? field.defaultAggregate : null,
    sort: null,
  }
}

function patchColumn(column: DesignerColumn, patch: Partial<Omit<DesignerColumn, 'uid' | 'field'>>): DesignerColumn {
  const next = { ...column, ...patch }
  if (patch.prefixOn === true && next.prefixLength === null && patch.prefixLength === undefined) next.prefixLength = DEFAULT_PREFIX_LENGTH
  if (patch.group === true && !column.group) next.aggregate = null
  return next
}

function moveTo(columns: DesignerColumn[], uid: number, to: number): DesignerColumn[] | null {
  const from = columns.findIndex((c) => c.uid === uid)
  if (from < 0) return null
  const target = Math.max(0, Math.min(to, columns.length - 1))
  if (target === from) return null
  const next = [...columns]
  const [moved] = next.splice(from, 1)
  if (!moved) return null
  next.splice(target, 0, moved)
  return next
}

function reduceColumns(state: DesignerState, action: DesignerAction, catalog: ReportCatalog): DesignerState | undefined {
  switch (action.type) {
    case 'addColumn': {
      if (state.columns.length >= catalog.limits.columnsMax) return state
      const column = newColumn(state.nextUid, action.field, hasGroup(state.columns))
      return { ...state, columns: [...state.columns, column], selectedUid: column.uid, nextUid: state.nextUid + 1 }
    }
    case 'removeColumn': {
      if (!state.columns.some((c) => c.uid === action.uid)) return state
      const columns = reconcileAggregates(
        state.columns.filter((c) => c.uid !== action.uid),
        catalog,
      )
      return {
        ...state,
        columns,
        selectedUid: state.selectedUid === action.uid ? null : state.selectedUid,
      }
    }
    case 'moveColumn': {
      const columns = moveTo(state.columns, action.uid, action.to)
      return columns ? { ...state, columns } : state
    }
    case 'selectColumn': {
      if (state.selectedUid === action.uid) return state
      if (action.uid !== null && !state.columns.some((c) => c.uid === action.uid)) return state
      return { ...state, selectedUid: action.uid }
    }
    case 'updateColumn': {
      const current = state.columns.find((c) => c.uid === action.uid)
      if (!current) return state
      const field = fieldByKey(catalog, current.field)
      if (action.patch.group === true && field && !field.groupable) return state
      const patched = state.columns.map((c) => (c.uid === action.uid ? patchColumn(c, action.patch) : c))
      const groupChanged = action.patch.group !== undefined && action.patch.group !== current.group
      return { ...state, columns: groupChanged ? reconcileAggregates(patched, catalog) : patched }
    }
    default:
      return undefined
  }
}

/** 컬럼 편집 뒤 차트가 가리키는 열이 없어졌거나 역할이 바뀌었으면 그 참조만 뺀다. */
function withChartReconciled(state: DesignerState): DesignerState {
  const chart = reconcileChart(state.chart, state.columns)
  return chart === state.chart ? state : { ...state, chart }
}

function reduceChart(state: DesignerState, action: DesignerAction): DesignerState | undefined {
  switch (action.type) {
    case 'createChart':
      return { ...state, chart: action.chart }
    case 'changeChart':
      return state.chart ? { ...state, chart: { ...state.chart, ...action.patch } } : state
    case 'setChartKind':
      return state.chart ? { ...state, chart: normalizeForKind(state.chart, action.kind, state.columns) } : state
    case 'removeChart':
      return state.chart ? { ...state, chart: null } : state
    default:
      return undefined
  }
}

function replaceCondition(state: DesignerState, uid: number, change: (c: DesignerCondition) => DesignerCondition): DesignerState {
  if (!state.conditions.some((c) => c.uid === uid)) return state
  return { ...state, conditions: state.conditions.map((c) => (c.uid === uid ? change(c) : c)) }
}

function reduceConditions(state: DesignerState, action: DesignerAction, catalog: ReportCatalog): DesignerState | undefined {
  switch (action.type) {
    case 'addCondition': {
      const operator = action.field.operators[0]
      if (state.conditions.length >= catalog.limits.conditionsMax || operator === undefined) return state
      const condition: DesignerCondition = { uid: state.nextUid, field: action.field.key, operator, draft: emptyDraft(action.field, operator, catalog) }
      return { ...state, conditions: [...state.conditions, condition], nextUid: state.nextUid + 1 }
    }
    case 'changeConditionField': {
      const operator = action.field.operators[0]
      if (operator === undefined) return state
      return replaceCondition(state, action.uid, (c) => ({ ...c, field: action.field.key, operator, draft: emptyDraft(action.field, operator, catalog) }))
    }
    case 'changeOperator':
      return replaceCondition(state, action.uid, (c) => {
        const field = fieldByKey(catalog, c.field)
        const draft = field ? emptyDraft(field, action.operator, catalog) : c.draft
        return { ...c, operator: action.operator, draft: draft.shape === c.draft.shape ? c.draft : draft }
      })
    case 'changeDraft':
      return replaceCondition(state, action.uid, (c) => ({ ...c, draft: action.draft }))
    case 'removeCondition':
      return state.conditions.some((c) => c.uid === action.uid) ? { ...state, conditions: state.conditions.filter((c) => c.uid !== action.uid) } : state
    default:
      return undefined
  }
}

/**
 * 설계 상태 전이(순수). 바뀌는 것이 없으면 같은 객체를 돌려준다. 카탈로그는 호출처가 클로저로 넘긴다.
 * 한도(컬럼 `columnsMax`, 조건 `conditionsMax`)에서는 추가를 무시한다.
 */
export function designerReducer(state: DesignerState, action: DesignerAction, catalog: ReportCatalog): DesignerState {
  const columnResult = reduceColumns(state, action, catalog)
  if (columnResult) return action.type === 'removeColumn' || action.type === 'updateColumn' ? withChartReconciled(columnResult) : columnResult
  const chartResult = reduceChart(state, action)
  if (chartResult) return chartResult
  const conditionResult = reduceConditions(state, action, catalog)
  if (conditionResult) return conditionResult
  switch (action.type) {
    case 'setCombine':
      return state.combine === action.combine ? state : { ...state, combine: action.combine }
    case 'setRowLimit':
      return state.rowLimit === action.rowLimit ? state : { ...state, rowLimit: action.rowLimit }
    case 'reset':
      return { ...initialDesignerState(catalog.limits), nextUid: state.nextUid }
    case 'load':
      return { ...action.state, nextUid: Math.max(action.state.nextUid, state.nextUid) }
    default:
      return state
  }
}
