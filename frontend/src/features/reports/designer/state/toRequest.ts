import type {
  ReportCatalog,
  ReportColumnInput,
  ReportConditionInput,
  ReportConditionValue,
  ReportField,
  ReportQueryInput,
} from '../../../../shared/model/reportTypes'
import { fieldByKey, isMoneyField } from './columnRules'
import type { ConditionDraft } from './conditionDraft'
import type { DesignerColumn, DesignerCondition, DesignerState } from './designerState'

/** 요청을 만들 수 없는 입력. `uid`는 조건 또는 컬럼(`prefix_length`), `part`는 그 입력 칸이다. */
export interface InputIssue {
  uid: number
  part: 'value' | 'low' | 'high' | 'day' | 'first' | 'last' | 'days' | 'prefix_length'
  message: string
}

export type RequestBuild =
  | { request: ReportQueryInput; columnUids: number[]; conditionUids: number[] }
  | { inputIssues: InputIssue[] }

const MONEY_UNIT = 1000
const WHOLE = /^-?\d+$/

function columnInput(column: DesignerColumn, field: ReportField | undefined): ReportColumnInput {
  const label = column.label.trim()
  return {
    field: column.field,
    ...(column.format !== null ? { format: column.format } : {}),
    group: column.group,
    ...(label !== '' && label !== field?.label ? { label } : {}),
    ...(column.prefixOn && column.prefixLength !== null ? { prefixLength: column.prefixLength } : {}),
    ...(column.aggregate !== null ? { aggregate: column.aggregate } : {}),
    ...(column.sort !== null ? { sort: column.sort } : {}),
  }
}

function columnIssues(column: DesignerColumn, max: number): InputIssue[] {
  if (!column.prefixOn) return []
  const n = column.prefixLength
  if (n !== null && Number.isInteger(n) && n >= 1 && n <= max) return []
  return [{ uid: column.uid, part: 'prefix_length', message: `1~${max} 사이 정수를 입력하세요` }]
}

/** 쉼표를 뺀 정수 문자열을 읽는다. 정수가 아니거나 safe integer를 넘으면 null(-0은 0). */
function parseWhole(text: string, unit: number): number | null {
  const cleaned = text.trim().replaceAll(',', '')
  if (!WHOLE.test(cleaned)) return null
  const value = Number(cleaned) * unit
  if (!Number.isSafeInteger(value)) return null
  return value === 0 ? 0 : value
}

interface Reading {
  value?: ReportConditionValue
  issues: Omit<InputIssue, 'uid'>[]
}

const ok = (value?: ReportConditionValue): Reading => (value === undefined ? { issues: [] } : { value, issues: [] })
const bad = (part: InputIssue['part'], message: string): Reading => ({ issues: [{ part, message }] })

function readNumbers(draft: { low: string; high: string }, unit: number, message: string): Reading {
  const low = parseWhole(draft.low, unit)
  const high = parseWhole(draft.high, unit)
  const issues: Reading['issues'] = []
  if (low === null) issues.push({ part: 'low', message })
  if (high === null) issues.push({ part: 'high', message })
  if (low === null || high === null) return { issues }
  if (low > high) return bad('high', '시작이 끝보다 클 수 없습니다')
  return ok([low, high])
}

function readDraft(draft: ConditionDraft, field: ReportField, catalog: ReportCatalog): Reading {
  const unit = isMoneyField(field) ? MONEY_UNIT : 1
  const wholeMessage = unit === MONEY_UNIT ? '천원 단위 정수로 입력하세요' : '정수로 입력하세요'
  switch (draft.shape) {
    case 'none':
      return ok()
    case 'text': {
      const text = draft.text.trim()
      return text === '' ? bad('value', '값을 입력하세요') : ok(text)
    }
    case 'list': {
      if (draft.values.length === 0) return bad('value', '하나 이상 선택하세요')
      return ok(field.valueKind === 'id' ? draft.values.map(Number) : draft.values)
    }
    case 'number': {
      const value = parseWhole(draft.text, unit)
      return value === null ? bad('value', wholeMessage) : ok(value)
    }
    case 'range':
      return readNumbers(draft, unit, wholeMessage)
    case 'date':
      return draft.day === '' ? bad('day', '날짜를 고르세요') : ok(draft.day)
    case 'date_range': {
      const issues: Reading['issues'] = []
      if (draft.first === '') issues.push({ part: 'first', message: '날짜를 고르세요' })
      if (draft.last === '') issues.push({ part: 'last', message: '날짜를 고르세요' })
      return issues.length > 0 ? { issues } : ok([draft.first, draft.last])
    }
    case 'relative': {
      const needsDays = catalog.relativePeriods.find((p) => p.key === draft.period)?.needsDays ?? false
      if (!needsDays) return ok({ period: draft.period })
      const max = catalog.limits.lastNDaysMax
      const days = parseWhole(draft.days, 1)
      if (days === null || days < 1 || days > max) return bad('days', `1~${max} 사이 정수를 입력하세요`)
      return ok({ period: draft.period, days })
    }
  }
}

function conditionInput(condition: DesignerCondition, catalog: ReportCatalog): { input?: ReportConditionInput; issues: InputIssue[] } {
  const field = fieldByKey(catalog, condition.field)
  if (!field) return { input: { field: condition.field, operator: condition.operator }, issues: [] }
  const reading = readDraft(condition.draft, field, catalog)
  if (reading.issues.length > 0) return { issues: reading.issues.map((i) => ({ uid: condition.uid, ...i })) }
  return {
    input: { field: condition.field, operator: condition.operator, ...(reading.value !== undefined ? { value: reading.value } : {}) },
    issues: [],
  }
}

/**
 * 설계를 조회 요청으로 바꾼다. 숫자·날짜·목록 값을 읽을 수 없으면 요청을 만들지 않고 입력 문제만 돌려준다.
 * 그룹핑·집계·한도 같은 정의 판정은 서버가 한다. `columnUids[i]`/`conditionUids[i]`는 요청 index → uid 대응이다.
 */
export function toReportRequest(state: DesignerState, catalog: ReportCatalog): RequestBuild {
  const conditions: ReportConditionInput[] = []
  const inputIssues: InputIssue[] = state.columns.flatMap((c) => columnIssues(c, catalog.limits.prefixMax))
  for (const condition of state.conditions) {
    const built = conditionInput(condition, catalog)
    inputIssues.push(...built.issues)
    if (built.input) conditions.push(built.input)
  }
  if (inputIssues.length > 0) return { inputIssues }
  return {
    request: {
      columns: state.columns.map((c) => columnInput(c, fieldByKey(catalog, c.field))),
      conditions,
      combine: state.combine,
      rowLimit: state.rowLimit,
    },
    columnUids: state.columns.map((c) => c.uid),
    conditionUids: state.conditions.map((c) => c.uid),
  }
}
