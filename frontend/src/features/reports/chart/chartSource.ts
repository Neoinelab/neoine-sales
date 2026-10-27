import type { ReportCatalog, ReportChartInput } from '../../../shared/model/reportTypes'
import type { DesignerAction, DesignerColumn } from '../designer/state/designerState'
import type { Message } from '../designer/state/issueView'
import type { ChartDraft } from './chartDraft'

/** 보기 화면: 저장된 차트를 읽기 전용으로 보인다(설정 패널 없음). */
export interface ChartViewSource {
  mode: 'view'
  chart: ReportChartInput | null
  /** 서버가 저장된 차트를 읽지 못했을 때의 안내 문구. */
  problem: string | null
}

/** 디자이너: 편집 중인 초안과 설정 패널. 컬럼 참조는 uid이고 마지막 조회의 열 대응(`resultColumnUids`)으로 결과 열을 찾는다. */
export interface ChartEditSource {
  mode: 'edit'
  draft: ChartDraft | null
  columns: readonly DesignerColumn[]
  catalog: ReportCatalog
  resultColumnUids: readonly number[]
  /** 저장 때 서버가 알려 준 차트 위반(수정하면 사라진다). */
  issues: readonly Message[]
  /** 서버가 저장된 차트를 읽지 못했을 때의 안내(보기 화면과 같은 문구). */
  problem?: string | null
  dispatch: (action: DesignerAction) => void
}

export type ChartSource = ChartViewSource | ChartEditSource
