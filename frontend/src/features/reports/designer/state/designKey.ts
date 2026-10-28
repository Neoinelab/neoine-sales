import type { ReportCatalog } from '../../../../shared/model/reportTypes'
import { toChartInput } from '../../chart/chartDraft'
import type { DesignerState } from './designerState'
import { toReportRequest } from './toRequest'

/**
 * 설계 내용을 나타내는 안정 문자열. uid·선택과 무관하게 내용이 같으면 같다.
 * 차트 설정(index 기준)도 키에 들어가므로 차트를 바꾸면 키가 달라지고 원래대로 돌리면 같아진다.
 * 요청으로 바꿀 수 있으면 그 요청의 JSON, 입력을 읽을 수 없으면 입력 초안 그대로의 JSON(편집 화면의 "저장 안 됨" 판정 기준).
 */
export function designKey(state: DesignerState, catalog: ReportCatalog): string {
  const built = toReportRequest(state, catalog)
  const chart = state.chart ? toChartInput(state.chart, state.columns) : null
  if ('request' in built) return JSON.stringify({ request: built.request, chart })
  return JSON.stringify({
    raw: {
      columns: state.columns.map((c) => ({ ...c, uid: 0 })),
      conditions: state.conditions.map((c) => ({ ...c, uid: 0 })),
      combine: state.combine,
      rowLimit: state.rowLimit,
    },
    chart,
  })
}
