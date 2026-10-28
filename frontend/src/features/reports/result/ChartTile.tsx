import { lazy, Suspense } from 'react'
import type { ReportResult } from '../../../shared/model/reportTypes'
import type { ChartSource } from '../chart/chartSource'
import { TileFrame } from './TileFrame'

/** 차트 본문은 처음 보일 때 받는 청크다(Chart.js를 디자이너·보기 화면 청크에 싣지 않는다). */
const ChartTab = lazy(() => import('../chart/ChartTab'))

interface ChartTileProps {
  source: ChartSource
  result: ReportResult | null
  /** 결과 탭이 한 번도 보이지 않았으면 차트 청크를 아직 불러오지 않는다(숨은 곳에서 크기 0으로 그리지 않게). */
  deferred?: boolean
  /** 디자이너: '차트 설정' 버튼으로 설정 패널을 열고 닫는다. */
  onToggleSettings?: () => void
}

/** 차트 타일: 디자이너는 머리의 '차트 설정' 버튼(차트가 있을 때)으로 설정 패널을 열고 닫고, 보기 화면에는 버튼이 없다. */
export function ChartTile({ source, result, deferred = false, onToggleSettings }: ChartTileProps) {
  const head =
    source.mode === 'edit' && source.draft !== null && onToggleSettings ? (
      <button type="button" aria-expanded={source.settingsOpen} onClick={onToggleSettings}>
        차트 설정
      </button>
    ) : undefined
  return (
    <TileFrame tile="chart" head={head}>
      {!deferred && (
        <Suspense fallback={<p className="hint">차트를 불러오는 중…</p>}>
          <ChartTab source={source} result={result} />
        </Suspense>
      )}
    </TileFrame>
  )
}
