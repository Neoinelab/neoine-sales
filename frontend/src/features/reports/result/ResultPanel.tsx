import type { ReactNode } from 'react'
import type { ReportLayout, ReportResult, ReportResultView, ReportTile } from '../../../shared/model/reportTypes'
import type { ChartSource } from '../chart/chartSource'
import { SqlViewer } from '../designer/SqlViewer'
import { ChartTile } from './ChartTile'
import { visibleTiles, type DropEdge } from './layout'
import { ResultTiles } from './ResultTiles'
import { TableTile } from './TableTile'
import { ViewModePicker } from './ViewModePicker'

interface ResultPanelProps {
  layout: ReportLayout
  onView: (view: ReportResultView) => void
  onPlace: (dragged: ReportTile, target: ReportTile, edge: DropEdge) => void
  result: ReportResult | null
  /** 조회마다 바뀌는 번호. 표 화면 상태(페이지·합계 행)를 새 결과에서 처음으로 되돌린다. */
  runId: number
  /** 마지막 조회 뒤 설계가 바뀌었다(디자이너). */
  stale?: boolean
  /** 서버가 만든 SQL(없으면 안내). */
  sql: string | null
  /** 차트 타일이 그릴 것: 디자이너는 편집 초안, 보기 화면은 저장된 차트(읽기 전용). */
  chart: ChartSource
  /** 결과 탭이 한 번도 보이지 않았으면 차트를 아직 그리지 않는다(디자이너). */
  chartDeferred?: boolean
  onToggleChartSettings?: () => void
  /** 보기 선택 줄에 덧붙일 것(보기 화면의 저장 상태·안내). */
  viewNote?: ReactNode
  /** 보기 선택 줄 아래에 놓일 알림(보기 화면의 저장 실패 등). */
  notice?: ReactNode
}

/** 디자이너 결과 탭과 보기 화면이 함께 쓰는 결과 영역: 보기 방식 · 타일(표, 차트) · 생성 SQL. */
export function ResultPanel({ layout, onView, onPlace, result, runId, stale = false, sql, chart, chartDeferred, onToggleChartSettings, viewNote, notice }: ResultPanelProps) {
  // 보기 화면에서 저장된 차트가 없으면 차트가 들어가는 보기 방식은 쓸 수 없고 표만 보인다(저장된 배치는 그대로 둔다).
  const chartAvailable = chart.mode === 'edit' || chart.chart !== null
  const tiles = visibleTiles(layout, chartAvailable)
  const view = chartAvailable ? layout.view : 'table'
  const problem = chart.mode === 'view' && chart.chart === null ? (chart.problem ?? '이 리포트에는 저장된 차트가 없습니다. 편집 화면에서 만들 수 있습니다.') : null

  return (
    <div className="report-results">
      {result && stale && (
        <p className="hint report-stale" aria-live="polite">
          설계가 바뀌었습니다. 작성 탭에서 &apos;조회&apos;를 눌러 다시 조회하세요
        </p>
      )}
      {problem && <p className="hint">{problem}</p>}
      <div className="report-view-bar">
        <ViewModePicker view={view} chartAvailable={chartAvailable} onChange={onView} />
        {viewNote}
      </div>
      {notice}
      <ResultTiles
        tiles={tiles}
        arrange={layout.arrange}
        onPlace={onPlace}
        nodes={{
          table: <TableTile key={runId} result={result} />,
          chart: <ChartTile source={chart} result={result} deferred={chartDeferred} onToggleSettings={onToggleChartSettings} />,
        }}
      />
      <SqlViewer sql={sql} />
    </div>
  )
}
