import type { ReportResult } from '../../../shared/model/reportTypes'
import { ChartEditor } from './ChartEditor'
import { ChartPreview } from './ChartPreview'
import type { ChartSource } from './chartSource'

interface ChartTabProps {
  source: ChartSource
  result: ReportResult | null
}

function Body({ source, result }: { source: ChartSource; result: ReportResult | null }) {
  if (source.mode === 'edit') {
    return (
      <>
        {source.problem && source.draft === null && <p className="hint">{source.problem}</p>}
        <ChartEditor source={source} result={result} />
      </>
    )
  }
  if (!source.chart) {
    return <p className="hint">{source.problem ?? '이 리포트에는 저장된 차트가 없습니다. 편집 화면에서 만들 수 있습니다.'}</p>
  }
  return result ? <ChartPreview input={source.chart} result={result} /> : <p className="hint">불러오는 중…</p>
}

/** 차트 타일의 본문(lazy 청크의 입구). Chart.js 코드는 이 파일 아래에서만 불러온다. */
export default function ChartTab({ source, result }: ChartTabProps) {
  return (
    <div className="report-pane">
      <Body source={source} result={result} />
    </div>
  )
}
