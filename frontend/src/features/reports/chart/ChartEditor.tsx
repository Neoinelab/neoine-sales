import { useMemo } from 'react'
import type { ReportResult } from '../../../shared/model/reportTypes'
import { columnName } from '../designer/names'
import { columnHeader } from '../designer/format/formatCell'
import { ChartPreview } from './ChartPreview'
import { ChartSettingsPanel } from './ChartSettingsPanel'
import { chartDraftIssues, chartInputFor, defaultChart, type ChartDraft } from './chartDraft'
import type { ChartEditSource } from './chartSource'

const NEEDS_GROUPING = '그룹핑한 결과로 차트를 만들 수 있습니다'
const TOO_MANY_GROUPS = '차트는 그룹핑 컬럼이 1~2개일 때 만들 수 있습니다'

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
  const { draft, columns, catalog, resultColumnUids, settingsOpen, dispatch } = source
  const headerOf = (uid: number): string => {
    const at = resultColumnUids.indexOf(uid)
    const shown = at < 0 ? undefined : result?.columns.find((c) => c.index === at)
    if (shown) return columnHeader(shown)
    const column = columns.find((c) => c.uid === uid)
    return column ? columnName(column, catalog) : ''
  }
  const groups = columns.filter((c) => c.group).length

  if (!draft) {
    const created = defaultChart(columns, headerOf)
    return (
      <div className="report-chart-empty">
        <button type="button" disabled={created === null} onClick={() => created && dispatch({ type: 'createChart', chart: created })}>
          차트 만들기
        </button>
        {groups === 0 && <p className="hint">{NEEDS_GROUPING}</p>}
        {groups > 2 && <p className="hint">{TOO_MANY_GROUPS}</p>}
        {groups > 0 && groups <= 2 && <p className="hint">그룹핑 컬럼은 범주(와 계열)로, 나머지 컬럼은 값으로 차트를 그립니다.</p>}
      </div>
    )
  }
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
