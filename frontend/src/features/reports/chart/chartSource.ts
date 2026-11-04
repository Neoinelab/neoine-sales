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
  /** 차트 타일 안의 설정 패널(종류·열·옵션과 '차트 삭제')을 보일지. 열림 상태는 디자이너가 쥐고 저장하지 않는다. */
  settingsOpen: boolean
  dispatch: (action: DesignerAction) => void
}

export type ChartSource = ChartViewSource | ChartEditSource

/** 차트 본문(`ChartTab`)이 받는 원천: 편집이면 초안이 이미 있다(초안이 없는 빈 상태는 차트 타일이 `ChartEmpty`로 보인다). */
export type ChartBodySource = ChartViewSource | (ChartEditSource & { draft: ChartDraft })

/** 차트 본문을 보일 수 있는 원천인지(보기 화면이거나 초안이 있는 편집). 아니면 초안이 없는 빈 상태다. */
export const hasChartBody = (source: ChartSource): source is ChartBodySource => source.mode === 'view' || source.draft !== null
