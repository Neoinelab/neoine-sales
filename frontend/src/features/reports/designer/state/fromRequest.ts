import { fromChartInput } from '../../chart/chartDraft'
import type { ReportCatalog, ReportChartInput, ReportConditionInput, ReportConditionValue, ReportField, ReportLimits, ReportQueryInput } from '../../../../shared/model/reportTypes'
import { fieldByKey, isMoneyField } from './columnRules'
import { emptyDraft, type ConditionDraft } from './conditionDraft'
import type { DesignerColumn, DesignerCondition, DesignerState } from './designerState'

const MONEY_UNIT = 1000

const isStringList = (value: unknown): value is string[] => Array.isArray(value) && value.every((v) => typeof v === 'string')
const isPair = <T>(value: unknown, test: (v: unknown) => v is T): value is [T, T] => Array.isArray(value) && value.length === 2 && test(value[0]) && test(value[1])
const isNumber = (v: unknown): v is number => typeof v === 'number'
const isString = (v: unknown): v is string => typeof v === 'string'

/** 서버가 저장한 금액(원) → 입력 칸의 천원 문자열. */
const thousands = (won: number, field: ReportField | undefined): string => String(field && isMoneyField(field) ? won / MONEY_UNIT : won)

/**
 * 조건 값을 입력 초안으로 되돌린다(`toRequest`의 역). 모양이 맞지 않는 값은 빈 초안으로 둔다.
 * 카탈로그에 없는 필드는 값을 잃어도 되므로 연산자 모양의 빈 초안을 쓴다(조회하면 서버가 위반으로 알려 준다).
 */
function draftOf(condition: ReportConditionInput, field: ReportField | undefined, catalog: ReportCatalog): ConditionDraft {
  const value: ReportConditionValue | undefined = condition.value
  const blank = field ? emptyDraft(field, condition.operator, catalog) : unknownFieldDraft(condition, catalog)
  switch (blank.shape) {
    case 'text':
      return isString(value) ? { shape: 'text', text: value } : blank
    case 'number':
      return isNumber(value) ? { shape: 'number', text: thousands(value, field) } : blank
    case 'range':
      return isPair(value, isNumber) ? { shape: 'range', low: thousands(value[0], field), high: thousands(value[1], field) } : blank
    case 'date':
      return isString(value) ? { shape: 'date', day: value } : blank
    case 'date_range':
      return isPair(value, isString) ? { shape: 'date_range', first: value[0], last: value[1] } : blank
    case 'list':
      return Array.isArray(value) && (isStringList(value) || value.every(isNumber)) ? { shape: 'list', values: value.map(String) } : blank
    case 'relative': {
      if (typeof value !== 'object' || value === null || Array.isArray(value) || !('period' in value)) return blank
      return { shape: 'relative', period: value.period, days: value.days === undefined ? '' : String(value.days) }
    }
    default:
      return blank
  }
}

function unknownFieldDraft(condition: ReportConditionInput, catalog: ReportCatalog): ConditionDraft {
  const shape = catalog.operators.find((o) => o.key === condition.operator)?.shape
  const dates = isPair(condition.value, isString)
  switch (shape) {
    case 'none':
      return { shape: 'none' }
    case 'list':
      return { shape: 'list', values: [] }
    case 'number':
      return { shape: 'number', text: '' }
    case 'range':
      return dates ? { shape: 'date_range', first: '', last: '' } : { shape: 'range', low: '', high: '' }
    case 'date':
      return { shape: 'date', day: '' }
    case 'relative':
      return { shape: 'relative', period: 'this_year', days: '' }
    default:
      return { shape: 'text', text: '' }
  }
}

/**
 * 저장된 정의(요청 모양) → 디자이너 상태. `toReportRequest`의 역변환이라 왕복하면 같은 요청이 나온다.
 * uid는 1부터 컬럼, 이어서 조건에 붙이고 `nextUid`는 그 위다. 선택은 비어 있다. 카탈로그에 없는 필드도 그대로 둔다.
 */
export function fromReportRequest(input: ReportQueryInput, catalog: ReportCatalog, limits: ReportLimits): DesignerState {
  let uid = 1
  const columns: DesignerColumn[] = input.columns.map((c) => ({
    uid: uid++,
    field: c.field,
    label: c.label ?? '',
    format: c.format,
    prefixLength: c.format === 'prefix' ? (c.prefixLength ?? null) : null,
    group: c.group,
    aggregate: c.aggregate ?? null,
  }))
  const conditions: DesignerCondition[] = input.conditions.map((c) => ({
    uid: uid++,
    field: c.field,
    operator: c.operator,
    draft: draftOf(c, fieldByKey(catalog, c.field), catalog),
  }))
  const sortColumn = input.sort ? columns[input.sort.column] : undefined
  return {
    columns,
    conditions,
    combine: input.combine,
    sort: input.sort && sortColumn ? { uid: sortColumn.uid, direction: input.sort.direction } : null,
    rowLimit: input.rowLimit || limits.defaultRowLimit,
    chart: null,
    selectedUid: null,
    nextUid: uid,
  }
}

/** 저장된 리포트(정의 + 차트)로 디자이너 상태를 만든다. 차트의 컬럼 index는 정의의 컬럼 uid로 바뀐다. */
export function fromSavedReport(report: { definition: ReportQueryInput; chart: ReportChartInput | null }, catalog: ReportCatalog, limits: ReportLimits): DesignerState {
  const state = fromReportRequest(report.definition, catalog, limits)
  return { ...state, chart: fromChartInput(report.chart, state.columns) }
}
