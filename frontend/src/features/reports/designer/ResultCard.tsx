import { useState } from 'react'
import type { ReportResult, ReportRunFailure } from '../../../shared/model/reportTypes'
import { ResultTable } from './ResultTable'
import { SqlViewer } from './SqlViewer'

/** 결과 카드 위쪽 알림에 보일 위반 한 줄(위치 이름 + 서버 문구). */
export interface SummaryItem {
  key: string
  where: string | null
  message: string
}

interface ResultCardProps {
  result: ReportResult | null
  failure: ReportRunFailure | null
  /** 보일 위반 목록(정의 위반일 때). 모두 고쳐져 비면 알림도 없다. */
  summary: readonly SummaryItem[]
  stale: boolean
  /** 마지막 조회가 성공했을 때 서버가 만든 SQL(없으면 안내 문구). */
  sql: string | null
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

/** 조회 결과: 실패 알림 · 설계 변경 안내 · 총 행/시간 · 합계 행 선택 · 표 · 생성 SQL. */
export function ResultCard({ result, failure, summary, stale, sql }: ResultCardProps) {
  const [showTotals, setShowTotals] = useState(false)
  return (
    <section className="report-card" aria-labelledby="report-result-title">
      <h2 id="report-result-title">결과</h2>
      {failure && <FailureAlert failure={failure} summary={summary} />}
      {result ? (
        <>
          {stale && (
            <p className="hint report-stale" aria-live="polite">
              설계가 바뀌었습니다. &apos;조회&apos;를 눌러 다시 조회하세요
            </p>
          )}
          <div className="report-result-head">
            <p className="hint">{totalLine(result)}</p>
            {result.totals && (
              <label className="report-check">
                <input type="checkbox" checked={showTotals} onChange={(e) => setShowTotals(e.target.checked)} />
                합계 행
              </label>
            )}
          </div>
          <ResultTable result={result} showTotals={showTotals} />
          {showTotals && result.dealNumbersOnce && (
            <p className="field-hint">한 Deal이 여러 그룹에 나오면 그룹마다 한 번씩 더하므로 그룹 값의 합이 합계 행보다 클 수 있습니다</p>
          )}
        </>
      ) : (
        !failure && <p className="hint">컬럼을 고르고 &apos;조회&apos;를 누르면 결과가 여기에 보입니다.</p>
      )}
      <SqlViewer sql={sql} />
    </section>
  )
}
