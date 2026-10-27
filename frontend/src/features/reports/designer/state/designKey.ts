import type { ReportCatalog } from '../../../../shared/model/reportTypes'
import type { DesignerState } from './designerState'
import { toReportRequest } from './toRequest'

/**
 * 설계 내용을 나타내는 안정 문자열. uid·선택과 무관하게 내용이 같으면 같다.
 * 요청으로 바꿀 수 있으면 그 요청의 JSON, 입력을 읽을 수 없으면 입력 초안 그대로의 JSON(편집 화면의 "저장 안 됨" 판정 기준).
 */
export function designKey(state: DesignerState, catalog: ReportCatalog): string {
  const built = toReportRequest(state, catalog)
  if ('request' in built) return JSON.stringify({ request: built.request })
  const sortIndex = state.sort ? state.columns.findIndex((c) => c.uid === state.sort?.uid) : -1
  return JSON.stringify({
    raw: {
      columns: state.columns.map((c) => ({ ...c, uid: 0 })),
      conditions: state.conditions.map((c) => ({ ...c, uid: 0 })),
      combine: state.combine,
      sort: state.sort ? { index: sortIndex, direction: state.sort.direction } : null,
      rowLimit: state.rowLimit,
    },
  })
}
