import type { ReportCatalog, ReportField, ReportOperator, ReportRelativePeriod } from '../../../../shared/model/reportTypes'

/** 연산자 모양별 입력 초안. 화면이 입력하는 그대로의 문자열을 갖고, 요청으로 바꾸는 일은 `toRequest`가 한다. */
export type ConditionDraft =
  | { shape: 'none' }
  | { shape: 'text'; text: string }
  | { shape: 'list'; values: string[] }
  | { shape: 'number'; text: string }
  | { shape: 'range'; low: string; high: string }
  | { shape: 'date'; day: string }
  | { shape: 'date_range'; first: string; last: string }
  | { shape: 'relative'; period: ReportRelativePeriod; days: string }

/** 필드·연산자에 맞는 빈 초안. `range`는 날짜·시각 필드면 날짜 범위다. */
export function emptyDraft(field: ReportField, operator: ReportOperator, catalog: ReportCatalog): ConditionDraft {
  const shape = catalog.operators.find((o) => o.key === operator)?.shape ?? 'text'
  switch (shape) {
    case 'none':
      return { shape: 'none' }
    case 'list':
      return { shape: 'list', values: [] }
    case 'number':
      return { shape: 'number', text: '' }
    case 'range':
      return field.type === 'date' || field.type === 'datetime' ? { shape: 'date_range', first: '', last: '' } : { shape: 'range', low: '', high: '' }
    case 'date':
      return { shape: 'date', day: '' }
    case 'relative':
      return { shape: 'relative', period: 'this_year', days: '' }
    default:
      return { shape: 'text', text: '' }
  }
}
