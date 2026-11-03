import { useMemo } from 'react'
import type { ReportResult } from '../../../shared/model/reportTypes'
import { ChartPreview } from './ChartPreview'
import { ChartSettingsPanel } from './ChartSettingsPanel'
import { chartDraftIssues, chartInputFor, type ChartDraft } from './chartDraft'
import { chartHeaderOf } from './chartHeaders'
import { ChartEmpty } from './ChartEmpty'
import type { ChartEditSource } from './chartSource'

function referencedUids(draft: ChartDraft): number[] {
  return [...(draft.categoryUid === null ? [] : [draft.categoryUid]), ...(draft.seriesUid === null ? [] : [draft.seriesUid]), ...draft.valueUids]
}

function Preview({ draft, source, result, incomplete }: { draft: ChartDraft; source: ChartEditSource; result: ReportResult | null; incomplete: boolean }) {
  const { resultColumnUids } = source
  const input = useMemo(() => chartInputFor(draft, resultColumnUids), [draft, resultColumnUids])
  if (incomplete) return <p className="hint">설정을 완성하면 차트가 그려집니다</p>
  if (!result) return <p className="hint">조회하면 차트가 그려집니다</p>
  if (referencedUids(draft).some((uid) => !resultColumnUids.includes(uid))) return <p className="hint">조회하면 차트에 반영됩니다</p>
  return <ChartPreview input={input} result={result} />
}

/** 디자이너의 차트 타일 본문: 차트가 없으면 만들기, 있으면 미리보기(+ 열려 있으면 설정 패널과 삭제). */
export function ChartEditor({ source, result }: { source: ChartEditSource; result: ReportResult | null }) {
  const { draft, columns, settingsOpen, dispatch } = source
  if (!draft) return <ChartEmpty source={source} result={result} />
  const headerOf = chartHeaderOf(source, result)
  const issues = chartDraftIssues(draft, columns)
  return (
    <div className={settingsOpen ? 'report-chart-wrap' : 'report-chart-wrap is-closed'}>
      <div className="report-chart-view">
        <Preview draft={draft} source={source} result={result} incomplete={issues.length > 0} />
      </div>
      {settingsOpen && (
        <div className="report-chart-side">
          <ChartSettingsPanel draft={draft} columns={columns} headerOf={headerOf} issues={issues} serverIssues={source.issues} dispatch={dispatch} />
          <button type="button" className="danger" onClick={() => dispatch({ type: 'removeChart' })}>
            차트 삭제
          </button>
        </div>
      )}
    </div>
  )
}
