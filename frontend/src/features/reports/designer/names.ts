import type { ReportCatalog } from '../../../shared/model/reportTypes'
import { fieldByKey } from './state/columnRules'
import type { DesignerColumn } from './state/designerState'

/** 컬럼의 표시 이름: 입력한 이름(공백 제외)이 있으면 그것, 없으면 필드 이름. */
export function columnName(column: DesignerColumn, catalog: ReportCatalog): string {
  return column.label.trim() || fieldByKey(catalog, column.field)?.label || column.field
}
