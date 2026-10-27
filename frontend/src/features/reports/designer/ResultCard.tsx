import { lazy, Suspense, useId, useState } from 'react'
import type { ReportResult, ReportRunFailure } from '../../../shared/model/reportTypes'
import type { ChartSource } from '../chart/chartSource'
import { ResultTable } from './ResultTable'
import { SqlViewer } from './SqlViewer'

/** 결과 카드 위쪽 알림에 보일 위반 한 줄(위치 이름 + 서버 문구). */
export interface SummaryItem {
  key: string
  where: string | null
  message: string
}

/** 차트 탭은 처음 열 때 받는 청크다(Chart.js를 디자이너 청크에 싣지 않는다). */
const ChartTab = lazy(() => import('../chart/ChartTab'))

export type ResultTab = 'table' | 'chart'

interface ResultCardProps {
  result: ReportResult | null
  failure: ReportRunFailure | null
  /** 보일 위반 목록(정의 위반일 때). 모두 고쳐져 비면 알림도 없다. */
  summary: readonly SummaryItem[]
  stale: boolean
  /** 마지막 조회가 성공했을 때 서버가 만든 SQL(없으면 안내 문구). */
  sql: string | null
  tab: ResultTab
  onTab: (tab: ResultTab) => void
  /** 차트 탭이 그릴 것: 디자이너는 편집 초안, 보기 화면은 저장된 차트(읽기 전용). */
  chart: ChartSource
}

const count = (n: number): string => n.toLocaleString('en-US')

function totalLine(result: ReportResult): string {
  const seconds = (result.elapsedMs / 1000).toFixed(2)
  const total = result.truncated
    ? `총 ${count(result.totalCount)}행 중 ${count(result.rows.length)}행 표시(최대 행 수 제한)`
    : `총 ${count(result.totalCount)}행`
  return `${total} · 조회 ${seconds}초`
}

function FailureAlert({ failure, summary }: { failure: ReportRunFailure; summary: readonly SummaryItem[] }) {
  if (failure.kind !== 'invalid' || failure.issues.length === 0) {
    return (
      <p role="alert" className="error">
        {failure.message}
      </p>
    )
  }
  if (summary.length === 0) return null
  return (
    <div role="alert" className="report-summary">
      <strong>고칠 곳 {summary.length}개</strong>
      <ul>
        {summary.map((item) => (
          <li key={item.key}>
            {item.where ? `${item.where}: ` : ''}
            {item.message}
          </li>
        ))}
      </ul>
    </div>
  )
}

function Tabs({ tab, onTab, baseId }: { tab: ResultTab; onTab: (tab: ResultTab) => void; baseId: string }) {
  const tabs: { key: ResultTab; label: string }[] = [
    { key: 'table', label: '결과 표' },
    { key: 'chart', label: '차트' },
  ]
  return (
    <div role="tablist" aria-label="결과 보기" className="report-tabs">
      {tabs.map(({ key, label }) => (
        <button
          key={key}
          type="button"
          role="tab"
          id={`${baseId}-tab-${key}`}
          aria-selected={tab === key}
          aria-controls={`${baseId}-panel`}
          className={tab === key ? 'is-active' : undefined}
          onClick={() => onTab(key)}
        >
          {label}
        </button>
      ))}
    </div>
  )
}

function TablePane({ result, showTotals, onShowTotals, failure }: { result: ReportResult | null; showTotals: boolean; onShowTotals: (on: boolean) => void; failure: boolean }) {
  if (!result) return failure ? null : <p className="hint">컬럼을 고르고 &apos;조회&apos;를 누르면 결과가 여기에 보입니다.</p>
  return (
    <>
      <div className="report-result-head">
        <p className="hint">{totalLine(result)}</p>
        {result.totals && (
          <label className="report-check">
            <input type="checkbox" checked={showTotals} onChange={(e) => onShowTotals(e.target.checked)} />
            합계 행
          </label>
        )}
      </div>
      <ResultTable result={result} showTotals={showTotals} />
      {showTotals && result.dealNumbersOnce && (
        <p className="field-hint">한 Deal이 여러 그룹에 나오면 그룹마다 한 번씩 더하므로 그룹 값의 합이 합계 행보다 클 수 있습니다</p>
      )}
    </>
  )
}

/** 조회 결과: 실패 알림 · 설계 변경 안내 · 탭(결과 표 / 차트) · 생성 SQL. */
export function ResultCard({ result, failure, summary, stale, sql, tab, onTab, chart }: ResultCardProps) {
  const [showTotals, setShowTotals] = useState(false)
  const baseId = useId()
  // 조회 결과나 차트가 생기기 전에는 탭 없이 안내만 보인다.
  const showTabs = result !== null || (chart.mode === 'edit' && chart.draft !== null)
  const active = showTabs ? tab : 'table'
  const panel = { id: `${baseId}-panel`, 'aria-labelledby': showTabs ? `${baseId}-tab-${active}` : undefined }
  return (
    <section className="report-card" aria-labelledby="report-result-title">
      <h2 id="report-result-title">결과</h2>
      {failure && <FailureAlert failure={failure} summary={summary} />}
      {result && stale && (
        <p className="hint report-stale" aria-live="polite">
          설계가 바뀌었습니다. &apos;조회&apos;를 눌러 다시 조회하세요
        </p>
      )}
      {showTabs && <Tabs tab={active} onTab={onTab} baseId={baseId} />}
      {active === 'table' ? (
        <div role={showTabs ? 'tabpanel' : undefined} {...panel} className="report-pane">
          <TablePane result={result} showTotals={showTotals} onShowTotals={setShowTotals} failure={failure !== null} />
        </div>
      ) : (
        // 탭 패널(role)은 차트 청크 안쪽에서 그린다: 불러오는 동안에는 패널이 아니라 안내만 보인다.
        <Suspense fallback={<p className="hint">차트를 불러오는 중…</p>}>
          <ChartTab source={chart} result={result} panel={panel} />
        </Suspense>
      )}
      <SqlViewer sql={sql} />
    </section>
  )
}
