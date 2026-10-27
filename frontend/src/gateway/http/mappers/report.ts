import type { Schemas } from '../../../shared/api/client'
import type {
  ReportCatalog,
  ReportCell,
  ReportField,
  ReportQueryInput,
  ReportResult,
  ReportResultColumn,
} from '../../../shared/model/reportTypes'
import { malformedResponse } from '../request'

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
      format: c.format,
      group: c.group,
      ...(c.label !== undefined ? { label: c.label } : {}),
      ...(c.prefixLength !== undefined ? { prefix_length: c.prefixLength } : {}),
      ...(c.aggregate !== undefined ? { aggregate: c.aggregate } : {}),
    })),
    conditions: input.conditions.map((c) => ({
      field: c.field,
      operator: c.operator,
      ...(c.value !== undefined ? { value: c.value } : {}),
    })),
    combine: input.combine,
    ...(input.sort ? { sort: { column: input.sort.column, direction: input.sort.direction } } : {}),
    row_limit: input.rowLimit,
  }
}
