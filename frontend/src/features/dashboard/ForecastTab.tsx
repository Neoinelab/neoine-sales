import { Link } from 'react-router'
import { AMOUNT_LABEL } from '../../shared/model/money'
import type { DashboardSummary, ForecastCell } from '../../shared/model/types'
import { AmountText } from '../../shared/ui/AmountText'
import { closingQuarterPath, quarterCellPath, quarterTotalPath, type DashboardScope } from './drillDown'
import { QuarterChart } from './QuarterChart'
import { ClosingAttention, ForecastTiles } from './Tiles'

interface Props {
  summary: DashboardSummary
  scope: DashboardScope
}

function CellLink({ to, cell }: { to: string; cell: ForecastCell | undefined }) {
  const { count, amount } = cell ?? { count: 0, amount: 0 }
  return (
    <Link to={to}>
      {count}건 · <AmountText amount={amount} />
    </Link>
  )
}

/** 분기 표: 차트와 같은 값을 글자로 보인다. 모든 셀이 Deal 목록 링크다. 선택한 Quarter 행은 `aria-current`. */
function QuarterTable({ summary, scope }: Props) {
  const { columns } = summary.forecast
  return (
    <div className="db-scroll">
      <table className="db-table" aria-label="분기별 Forecast 구분 금액">
        <caption className="hint">셀 값: 건수 · {AMOUNT_LABEL}</caption>
        <thead>
          <tr>
            <th scope="col">분기</th>
            {columns.map((c) => (
              <th key={c.key} scope="col" className="db-num">
                {c.name}
              </th>
            ))}
            <th scope="col" className="db-num">
              Open 합계
            </th>
            <th scope="col" className="db-num">
              합계
            </th>
          </tr>
        </thead>
        <tbody>
          {summary.quarters.map((q) => (
            <tr key={q.quarter} aria-current={scope.quarter === q.quarter ? 'true' : undefined} className={scope.quarter === q.quarter ? 'db-selected' : undefined}>
              <th scope="row">Q{q.quarter}</th>
              {columns.map((c) => (
                <td key={c.key} className="db-num">
                  <CellLink to={quarterCellPath(scope, q.quarter, c.key)} cell={q.cells[c.key]} />
                </td>
              ))}
              <td className="db-num">
                <CellLink to={closingQuarterPath(scope, { year: scope.year, quarter: q.quarter })} cell={q.openTotal} />
              </td>
              <td className="db-num db-total">
                <CellLink to={quarterTotalPath(scope, q.quarter)} cell={q.total} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Forecast 탭(슬라이드 9): Forecast 구분별 타일 → Quarter Closing Forecast(누적 막대 + 표) → Closing Attention. */
export function ForecastTab({ summary, scope }: Props) {
  return (
    <div className="db-stack">
      <ForecastTiles summary={summary} scope={scope} />
      <section className="db-panel" aria-labelledby="db-quarter-heading">
        <h2 id="db-quarter-heading">Quarter Closing Forecast</h2>
        <p className="hint">
          Expected Close가 속한 분기별 Forecast 구분 금액입니다(Lost 제외). 선택한 Quarter와 관계없이 4개 분기를 모두 보입니다.
        </p>
        {scope.quarter !== undefined && <p className="db-selected-note">Selected Quarter: Q{scope.quarter}</p>}
        <QuarterChart columns={summary.forecast.columns} quarters={summary.quarters} scope={scope} />
        <QuarterTable summary={summary} scope={scope} />
      </section>
      <ClosingAttention summary={summary} scope={scope} />
    </div>
  )
}
