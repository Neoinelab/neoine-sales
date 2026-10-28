import { useState } from 'react'
import type { ReportResult } from '../../../shared/model/reportTypes'
import { ResultTable } from '../designer/ResultTable'
import { TileFrame } from './TileFrame'

const count = (n: number): string => n.toLocaleString('en-US')

function totalLine(result: ReportResult): string {
  const seconds = (result.elapsedMs / 1000).toFixed(2)
  const total = result.truncated
    ? `총 ${count(result.totalCount)}행 중 ${count(result.rows.length)}행 표시(최대 행 수 제한)`
    : `총 ${count(result.totalCount)}행`
  return `${total} · 조회 ${seconds}초`
}

/** 표 타일: 머리에 총 행 수·조회 시간과 합계 행 선택, 본문에 결과 표. 결과가 없으면 안내만 보인다. */
export function TableTile({ result }: { result: ReportResult | null }) {
  const [showTotals, setShowTotals] = useState(false)
  const head = result ? (
    <>
      <span className="hint">{totalLine(result)}</span>
      {result.totals && (
        <label className="report-check">
          <input type="checkbox" checked={showTotals} onChange={(e) => setShowTotals(e.target.checked)} />
          합계 행
        </label>
      )}
    </>
  ) : undefined
  return (
    <TileFrame tile="table" head={head}>
      {result ? (
        <>
          <ResultTable result={result} showTotals={showTotals} />
          {showTotals && result.dealNumbersOnce && (
            <p className="field-hint">한 Deal이 여러 그룹에 나오면 그룹마다 한 번씩 더하므로 그룹 값의 합이 합계 행보다 클 수 있습니다</p>
          )}
        </>
      ) : (
        <p className="hint">아직 조회 결과가 없습니다. 작성 탭에서 &apos;조회&apos;를 누르세요.</p>
      )}
    </TileFrame>
  )
}
