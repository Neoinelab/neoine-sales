import type { Schemas } from '../../../shared/api/client'
import type {
  ReportAggregate,
  ReportCatalog,
  ReportCell,
  ReportColumnInput,
  ReportCombine,
  ReportConditionInput,
  ReportConditionValue,
  ReportField,
  ReportFormat,
  ReportOperator,
  ReportQueryInput,
  ReportResult,
  ReportResultColumn,
  ReportVisibility,
  SavedReport,
  SavedReportSummary,
} from '../../../shared/model/reportTypes'
import { malformedResponse } from '../request'
import { toChart, toChartKind } from './reportChart'
import { toUserRef } from './user'

type Field = Schemas['ReportFieldResponse']
type ResultColumn = Schemas['ReportResultColumn']

function toField(f: Field): ReportField {
  return {
    key: f.key,
    label: f.label,
    entity: f.entity,
    type: f.type,
    formats: [...f.formats],
    defaultFormat: f.default_format,
    unit: f.unit,
    operators: [...f.operators],
    aggregates: [...f.aggregates],
    defaultAggregate: f.default_aggregate,
    groupable: f.groupable,
    filterable: f.filterable,
    requiresGrouping: f.requires_grouping,
    dealNumber: f.deal_number,
    valueKind: f.value_kind,
    options: f.options ? f.options.map((o) => ({ value: o.value, label: o.label })) : null,
    optionsSource: f.options_source,
    optionsCategory: f.options_category,
  }
}

/** 카탈로그 응답(snake_case) → 화면 모델. 연산자의 입력 모양 키는 서버에서 `value`이고 모델에서는 `shape`다. */
export function toCatalog(body: Schemas['ReportCatalogResponse']): ReportCatalog {
  const l = body.limits
  return {
    limits: {
      columnsMin: l.columns_min,
      columnsMax: l.columns_max,
      conditionsMax: l.conditions_max,
      rowLimits: [...l.row_limits],
      defaultRowLimit: l.default_row_limit,
      statementTimeoutSeconds: l.statement_timeout_seconds,
      textValueMax: l.text_value_max,
      listValueMax: l.list_value_max,
      lastNDaysMax: l.last_n_days_max,
      labelMax: l.label_max,
      prefixMax: l.prefix_max,
    },
    entities: body.entities.map((e) => ({ key: e.key, label: e.label })),
    formats: body.formats.map((f) => ({ key: f.key, label: f.label, affectsQuery: f.affects_query })),
    operators: body.operators.map((o) => ({ key: o.key, label: o.label, shape: o.value })),
    aggregates: body.aggregates.map((a) => ({ key: a.key, label: a.label })),
    relativePeriods: body.relative_periods.map((p) => ({ key: p.key, label: p.label, needsDays: p.needs_days })),
    fields: body.fields.map(toField),
  }
}

/** 셀은 문자열·숫자·null만 허용한다(계약 밖 값은 화면이 읽을 수 없다). */
function toCell(value: unknown): ReportCell {
  if (value === null || typeof value === 'string' || typeof value === 'number') return value
  throw malformedResponse()
}

function toRow(row: readonly unknown[], width: number): ReportCell[] {
  if (!Array.isArray(row) || row.length !== width) throw malformedResponse()
  return row.map(toCell)
}

function toResultColumn(c: ResultColumn): ReportResultColumn {
  return {
    index: c.index,
    field: c.field,
    label: c.label,
    entity: c.entity,
    type: c.type,
    valueType: c.value_type,
    format: c.format,
    unit: c.unit,
    prefixLength: c.prefix_length,
    group: c.group,
    aggregate: c.aggregate,
  }
}

/** 조회 응답 → 화면 모델. 행·합계 행의 길이가 열 수와 다르거나 셀 모양이 계약과 다르면 malformed-response. */
export function toResult(body: Schemas['ReportQueryResponse']): ReportResult {
  const columns = body.columns.map(toResultColumn)
  const width = columns.length
  return {
    rowScope: body.row_scope,
    actionFilter: body.action_filter,
    dealNumbersOnce: body.deal_numbers_once,
    columns,
    rows: body.rows.map((row) => toRow(row, width)),
    totals: body.totals === null ? null : toRow(body.totals, width),
    totalCount: body.total_count,
    truncated: body.truncated,
    rowLimit: body.row_limit,
    sql: body.sql,
    elapsedMs: body.elapsed_ms,
    today: body.today,
  }
}

/** 설계 → 요청 본문(snake_case). 없는 값의 키는 보내지 않는다(서버가 알 수 없는 키를 거부한다). */
export function toQueryBody(input: ReportQueryInput): Schemas['ReportQueryRequest'] {
  return {
    columns: input.columns.map((c) => ({
      field: c.field,
      ...(c.format !== undefined ? { format: c.format } : {}),
      group: c.group,
      ...(c.label !== undefined ? { label: c.label } : {}),
      ...(c.prefixLength !== undefined ? { prefix_length: c.prefixLength } : {}),
      ...(c.aggregate !== undefined ? { aggregate: c.aggregate } : {}),
      ...(c.sort !== undefined ? { sort: c.sort } : {}),
    })),
    conditions: input.conditions.map((c) => ({
      field: c.field,
      operator: c.operator,
      ...(c.value !== undefined ? { value: c.value } : {}),
    })),
    combine: input.combine,
    row_limit: input.rowLimit,
  }
}

// ── 저장 리포트 ──────────────────────────────────────────────

function toVisibility(value: string): ReportVisibility {
  if (value === 'public' || value === 'private') return value
  throw malformedResponse()
}

type Head = Pick<Schemas['ReportSummaryResponse'], 'id' | 'name' | 'description' | 'visibility' | 'owner' | 'updated_by' | 'entities' | 'created_at' | 'updated_at'>

function toHead(body: Head): Omit<SavedReportSummary, 'chartKind'> {
  return {
    id: body.id,
    name: body.name,
    description: body.description,
    visibility: toVisibility(body.visibility),
    owner: toUserRef(body.owner),
    updatedBy: toUserRef(body.updated_by),
    entities: [...body.entities],
    createdAt: body.created_at,
    updatedAt: body.updated_at,
  }
}

export function toSummary(body: Schemas['ReportSummaryResponse']): SavedReportSummary {
  return { ...toHead(body), chartKind: body.chart_kind === null ? null : toChartKind(body.chart_kind) }
}

function toColumnInput(c: Schemas['ReportColumnRequest']): ReportColumnInput {
  return {
    field: c.field,
    ...(typeof c.format === 'string' ? { format: c.format as ReportFormat } : {}),
    group: c.group,
    ...(typeof c.label === 'string' ? { label: c.label } : {}),
    ...(typeof c.prefix_length === 'number' ? { prefixLength: c.prefix_length } : {}),
    ...(typeof c.aggregate === 'string' ? { aggregate: c.aggregate as ReportAggregate } : {}),
    ...(c.sort === 'asc' || c.sort === 'desc' ? { sort: c.sort } : {}),
  }
}

function toConditionInput(c: Schemas['ReportConditionRequest']): ReportConditionInput {
  return {
    field: c.field,
    operator: c.operator as ReportOperator,
    ...(c.value !== undefined && c.value !== null ? { value: c.value as ReportConditionValue } : {}),
  }
}

/** 저장된 정의(서버 요청 모양, snake_case) → 화면의 요청 모델. 없는 키는 두지 않는다. */
export function toDefinition(body: Schemas['ReportQueryRequest']): ReportQueryInput {
  return {
    columns: body.columns.map(toColumnInput),
    conditions: (body.conditions ?? []).map(toConditionInput),
    combine: body.combine as ReportCombine,
    rowLimit: body.row_limit as number,
  }
}

export function toSavedReport(body: Schemas['ReportDetailResponse']): SavedReport {
  return {
    ...toHead(body),
    revision: body.revision,
    definition: toDefinition(body.definition),
    generatedSql: body.generated_sql,
    chart: body.chart === null ? null : toChart(body.chart),
    chartProblem: body.chart_problem,
  }
}
