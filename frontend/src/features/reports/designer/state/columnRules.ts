import type { ReportAggregate, ReportCatalog, ReportField } from '../../../../shared/model/reportTypes'

/**
 * 카탈로그 기반 선택지 규칙. 화면은 서버가 거부할 조합을 미리 막지 않고(최종 판정은 서버),
 * 선택지만 카탈로그에서 좁혀 보여 준다.
 */

/** 고를 수 있는 집계. 목록이 비어 있고 기본 집계만 있으면(Action 건수) 그것 하나로 고정이다. */
export function aggregateChoices(field: ReportField): ReportAggregate[] {
  if (field.aggregates.length > 0) return field.aggregates
  return field.defaultAggregate ? [field.defaultAggregate] : []
}

/** 집계를 바꿀 수 없는 필드(선택지가 기본 집계 하나뿐). */
export function isAggregateLocked(field: ReportField): boolean {
  return field.aggregates.length === 0 && field.defaultAggregate !== null
}

/** 조건에 쓸 수 있는 필드(`filterable`). */
export function filterableFields(catalog: ReportCatalog): ReportField[] {
  return catalog.fields.filter((f) => f.filterable)
}

export function fieldByKey(catalog: ReportCatalog, key: string): ReportField | undefined {
  return catalog.fields.find((f) => f.key === key)
}

/** 금액 필드: 조건 값을 천원 단위로 입력받는다. */
export function isMoneyField(field: ReportField): boolean {
  return field.type === 'number' && field.defaultFormat === 'krw_thousand'
}
