import { useState } from 'react'
import { useToday } from '../../../data/today'
import type { ReportResult } from '../../../shared/model/reportTypes'
import { Pager } from '../../../shared/ui/Pager'
import { cellTitle, columnHeader, formatCell, formatShownCell, isNumericColumn } from './format/formatCell'

const PAGE_SIZE = 100

interface ResultTableProps {
  result: ReportResult
  /** 합계 행을 표 맨 아래에 보일지(합계 행이 있는 결과만). */
  showTotals: boolean
}

/** 결과 표. 100행씩 나누어 보이고, 합계 행(첫 그룹 열에 "합계")은 `tfoot`에 둔다. */
export function ResultTable({ result, showTotals }: ResultTableProps) {
  const { now, today } = useToday()
  const [offset, setOffset] = useState(0)
  const ctx = { now, today, totals: result.totals }
  const firstGroup = result.columns.findIndex((c) => c.group)
  const page = result.rows.slice(offset, offset + PAGE_SIZE)
  const totals = showTotals ? result.totals : null

  return (
    <>
      <div className="report-scroll">
        <table>
          <caption className="report-sr">조회 결과</caption>
          <thead>
            <tr>
              {result.columns.map((column) => (
                <th key={column.index} scope="col" className={isNumericColumn(column) ? 'report-num' : undefined}>
                  {columnHeader(column)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {page.map((row, r) => (
              <tr key={offset + r}>
                {result.columns.map((column, c) => {
                  const value = row[c] ?? null
                  return (
                    <td key={column.index} className={isNumericColumn(column) ? 'report-num' : 'report-text'} title={cellTitle(value, column, ctx)}>
                      {formatShownCell(value, column, ctx)}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
          {totals && (
            <tfoot>
              <tr>
                {result.columns.map((column, c) => (
                  <td key={column.index} className={isNumericColumn(column) ? 'report-num' : 'report-text'}>
                    {c === firstGroup ? '합계' : formatCell(totals[c] ?? null, column, ctx)}
                  </td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {result.rows.length > PAGE_SIZE && <Pager offset={offset} limit={PAGE_SIZE} total={result.rows.length} onChange={setOffset} />}
    </>
  )
}
