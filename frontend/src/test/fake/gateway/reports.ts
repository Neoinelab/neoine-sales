import type { ReportsGateway } from '../../../gateway/types'
import type {
  ReportAggregate,
  ReportCatalog,
  ReportCell,
  ReportColumnInput,
  ReportField,
  ReportIssue,
  ReportQueryInput,
  ReportResult,
  ReportResultColumn,
  ReportValueType,
} from '../../../shared/model/reportTypes'
import { invalidReport } from '../errors'
import { REPORT_CATALOG } from '../seed/reportCatalog'
import { clone, read, requireUser, type MockContext } from './context'
import type { ReportQueryHandler } from '../store'
import { createSavedReportsGateway } from './savedReports'

/**
 * 리포트 Fake. 서버 규칙 중 컬럼·조건 개수·집계·그룹핑·행 수 위반만 서버와 같은 code·location·문구로 흉내 낸다.
 * 조건 값(숫자·날짜·목록)은 검증하지 않는다. 테스트가 `control.setReportQueryHandler`로 응답을 정하면 규칙·합성 결과 대신 그것을 쓴다.
 */

const KEY_ECHO_MAX = 50
const SYNTHETIC_ROWS = 3
const SYNTHETIC_ELAPSED_MS = 21

const aggregateLabel = (catalog: ReportCatalog, key: ReportAggregate): string =>
  catalog.aggregates.find((a) => a.key === key)?.label ?? key

function allowedAggregates(field: ReportField): ReportAggregate[] {
  if (field.aggregates.length > 0) return field.aggregates
  return field.defaultAggregate ? [field.defaultAggregate] : []
}

const unknownField = (key: string) => `허용되지 않은 필드입니다: ${key.slice(0, KEY_ECHO_MAX)}`

function columnIssues(catalog: ReportCatalog, input: ReportQueryInput): ReportIssue[] {
  const { limits } = catalog
  if (input.columns.length < limits.columnsMin || input.columns.length > limits.columnsMax) {
    return [
      {
        location: ['columns'],
        code: 'columns-count',
        message: `컬럼은 ${limits.columnsMin}개 이상 ${limits.columnsMax}개 이하로 지정하세요`,
      },
    ]
  }
  const grouped = input.columns.some((c) => c.group)
  const issues: ReportIssue[] = []
  input.columns.forEach((column, i) => {
    const field = catalog.fields.find((f) => f.key === column.field)
    if (!field) {
      issues.push({ location: ['columns', i, 'field'], code: 'unknown-field', message: unknownField(column.field) })
      return
    }
    issues.push(...aggregateIssues(catalog, field, column, i, grouped))
  })
  return issues
}

function aggregateIssues(
  catalog: ReportCatalog,
  field: ReportField,
  column: ReportColumnInput,
  i: number,
  grouped: boolean,
): ReportIssue[] {
  const at = (part?: string): (string | number)[] => (part ? ['columns', i, part] : ['columns', i])
  if (column.group) {
    if (!field.groupable) return [{ location: at('group'), code: 'group-not-allowed', message: '이 필드는 그룹핑할 수 없습니다' }]
    if (column.aggregate !== undefined) {
      return [{ location: at('aggregate'), code: 'aggregate-not-allowed', message: '그룹 컬럼에는 집계를 지정할 수 없습니다' }]
    }
    return []
  }
  if (!grouped) {
    if (field.requiresGrouping) {
      return [{ location: at(), code: 'grouping-required', message: '이 컬럼은 그룹핑할 때만 쓸 수 있습니다. 그룹 컬럼을 추가하세요' }]
    }
    if (column.aggregate !== undefined) {
      return [
        {
          location: at('aggregate'),
          code: 'aggregate-not-allowed',
          message: '그룹핑이 없으면 집계를 지정할 수 없습니다. 그룹 컬럼을 추가하거나 집계를 빼세요',
        },
      ]
    }
    return []
  }
  const allowed = allowedAggregates(field)
  const names = allowed.map((a) => aggregateLabel(catalog, a)).join(' 또는 ')
  if (column.aggregate === undefined) {
    if (field.defaultAggregate !== null) return []
    return [
      {
        location: at('aggregate'),
        code: 'aggregate-required',
        message: `그룹핑할 때 이 컬럼은 집계(${names})를 골라야 합니다. 그룹핑하거나 빼세요`,
      },
    ]
  }
  if (!allowed.includes(column.aggregate)) {
    return [
      {
        location: at('aggregate'),
        code: 'aggregate-not-allowed',
        message: `그룹핑할 때 이 컬럼은 ${names}만 고를 수 있습니다. 그룹핑하거나 빼세요`,
      },
    ]
  }
  return []
}

function conditionIssues(catalog: ReportCatalog, input: ReportQueryInput): ReportIssue[] {
  const max = catalog.limits.conditionsMax
  if (input.conditions.length > max) {
    return [{ location: ['conditions'], code: 'conditions-count', message: `조건은 ${max}개까지 지정할 수 있습니다` }]
  }
  const issues: ReportIssue[] = []
  input.conditions.forEach((condition, i) => {
    if (!catalog.fields.some((f) => f.key === condition.field)) {
      issues.push({ location: ['conditions', i, 'field'], code: 'unknown-field', message: unknownField(condition.field) })
    }
  })
  return issues
}

export function violations(catalog: ReportCatalog, input: ReportQueryInput): ReportIssue[] {
  const issues = [...columnIssues(catalog, input), ...conditionIssues(catalog, input)]
  if (!catalog.limits.rowLimits.includes(input.rowLimit)) {
    issues.push({
      location: ['row_limit'],
      code: 'row-limit-invalid',
      message: `최대 행 수는 ${catalog.limits.rowLimits.join(', ')} 중 하나여야 합니다`,
    })
  }
  return issues
}

function valueTypeOf(field: ReportField, column: ReportColumnInput, aggregate: ReportAggregate | null): ReportValueType {
  if (aggregate === 'count' || aggregate === 'count_distinct') return 'integer'
  if (aggregate === 'avg') return 'decimal'
  if (field.type === 'number') return 'integer'
  if (field.type === 'date' || field.type === 'datetime') {
    if (column.format === 'year') return 'integer'
    if (column.format === 'quarter' || column.format === 'month') return 'text'
    return field.type === 'date' || column.format === 'ymd' ? 'date' : 'datetime'
  }
  return 'text'
}

function aggregateOf(field: ReportField, column: ReportColumnInput, grouped: boolean): ReportAggregate | null {
  if (!grouped || column.group) return null
  return column.aggregate ?? field.defaultAggregate
}

/** 서버 `definition.py`와 같은 판정: Action 필드가 컬럼에 있으면 Action 행, 조건에만 있으면 EXISTS. */
function scopeOf(catalog: ReportCatalog, input: ReportQueryInput, columns: ReportResultColumn[]) {
  const entityOf = (key: string) => catalog.fields.find((f) => f.key === key)?.entity
  const rowScope = input.columns.some((c) => entityOf(c.field) === 'action') ? 'action' : 'deal'
  const actionFilter =
    rowScope === 'action' ? 'join' : input.conditions.some((c) => entityOf(c.field) === 'action') ? 'exists' : 'none'
  const dealNumbersOnce =
    rowScope === 'action' &&
    columns.some((c) => c.group) &&
    columns.some(
      (c) =>
        !c.group &&
        catalog.fields.find((f) => f.key === c.field)?.dealNumber === true &&
        (c.aggregate === 'sum' || c.aggregate === 'avg'),
    )
  return { rowScope, actionFilter, dealNumbersOnce } as const
}

/** 값 모양별 결정적 값: 행 r(0부터)의 text는 `<라벨> <r+1>`, integer는 (r+1)*1000, decimal은 (r+1)*1.5. */
function cellOf(column: ReportResultColumn, r: number): ReportCell {
  switch (column.valueType) {
    case 'integer':
      return column.format === 'year' ? 2026 - r : (r + 1) * 1000
    case 'decimal':
      return (r + 1) * 1.5
    case 'date':
      return `2026-10-0${r + 1}`
    case 'datetime':
      return `2026-10-0${r + 1}T09:00:00+09:00`
    default:
      return `${column.label} ${r + 1}`
  }
}

function synthesize(ctx: MockContext, catalog: ReportCatalog, input: ReportQueryInput): ReportResult {
  const grouped = input.columns.some((c) => c.group)
  const columns: ReportResultColumn[] = input.columns.map((column, index) => {
    const field = catalog.fields.find((f) => f.key === column.field) as ReportField
    const aggregate = aggregateOf(field, column, grouped)
    return {
      index,
      field: field.key,
      label: column.label ?? field.label,
      entity: field.entity,
      type: field.type,
      valueType: valueTypeOf(field, column, aggregate),
      format: column.format ?? field.defaultFormat,
      unit: field.unit,
      prefixLength: column.prefixLength ?? null,
      group: column.group,
      aggregate,
    }
  })
  const rows = Array.from({ length: SYNTHETIC_ROWS }, (_, r) => columns.map((column) => cellOf(column, r)))
  const totals: ReportCell[] | null = grouped
    ? columns.map((column, i) => {
        if (column.group || (column.aggregate !== 'sum' && column.aggregate !== 'count' && column.aggregate !== 'count_distinct')) return null
        return rows.reduce((sum, row) => sum + (row[i] as number), 0)
      })
    : null
  return {
    ...scopeOf(catalog, input, columns),
    columns,
    rows,
    totals,
    totalCount: SYNTHETIC_ROWS,
    truncated: false,
    rowLimit: input.rowLimit,
    sql: 'SELECT … /* fake */',
    elapsedMs: SYNTHETIC_ELAPSED_MS,
    today: ctx.clock.today(),
  }
}

/** 조회 한 번의 계획: 지정 응답(handler)이 있으면 그것을, 없으면 규칙 검사 뒤 합성 결과를 쓴다. 위반이면 던진다. */
export interface QueryPlan {
  handler: ReportQueryHandler | null
  result: ReportResult | null
}

/** 요청 기록(`record`)과 규칙 검사. `/query`만 설계 요청 기록에 남기고, 저장 리포트 실행은 따로 기록한다. */
export function planQuery(ctx: MockContext, input: ReportQueryInput, record: boolean): QueryPlan {
  const { reports } = ctx.store
  if (record) reports.queries.push(clone(input))
  if (reports.handler) return { handler: reports.handler, result: null }
  const issues = violations(REPORT_CATALOG, input)
  if (issues.length > 0) throw invalidReport(issues)
  return { handler: null, result: synthesize(ctx, REPORT_CATALOG, input) }
}

export async function settlePlan(plan: QueryPlan, input: ReportQueryInput): Promise<ReportResult> {
  if (plan.handler) return clone(await plan.handler(input))
  return plan.result as ReportResult
}

export function createReportsGateway(ctx: MockContext): ReportsGateway {
  return {
    fields: () =>
      read(ctx, () => {
        requireUser(ctx)
        return clone(REPORT_CATALOG)
      }),
    query: async (input) => {
      const plan = await read(ctx, () => {
        requireUser(ctx)
        return planQuery(ctx, input, true)
      })
      return settlePlan(plan, input)
    },
    ...createSavedReportsGateway(ctx, { issuesOf: (input) => violations(REPORT_CATALOG, input), planQuery, settlePlan }),
  }
}
