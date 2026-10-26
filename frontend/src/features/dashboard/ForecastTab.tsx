import { DrillLink } from './DrillLink'
import { AMOUNT_LABEL } from '../../shared/model/money'
import type { DashboardSummary, ForecastCell } from '../../shared/model/types'
import { AmountText } from '../../shared/ui/AmountText'
import { closingQuarterPath, forecastSetsOf, quarterCellPath, quarterTotalPath, type DashboardScope } from './drillDown'
import { QuarterChart } from './QuarterChart'
import { SelectedQuarterSection } from './SelectedQuarterSection'
import { ClosingAttention, ForecastTiles } from './Tiles'

interface Props {
  summary: DashboardSummary
  scope: DashboardScope
  selectedQuarter: 1 | 2 | 3 | 4
  onSelectQuarter: (quarter: 1 | 2 | 3 | 4) => void
}

function CellLink({ to, cell }: { to: string | null; cell: ForecastCell | undefined }) {
  const { count, amount } = cell ?? { count: 0, amount: 0 }
  return (
    <DrillLink to={to}>
      {count}건 · <AmountText amount={amount} />
    </DrillLink>
  )
}

/** 분기 표: 차트와 같은 값을 글자로 보인다. 모든 셀이 Deal 목록 링크다. Selected Quarter 행은 `aria-current`. */
function QuarterTable({ summary, scope, selectedQuarter }: Pick<Props, 'summary' | 'scope' | 'selectedQuarter'>) {
  const { columns } = summary.forecast
  const sets = forecastSetsOf(columns)
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
            <tr key={q.quarter} aria-current={selectedQuarter === q.quarter ? 'true' : undefined} className={selectedQuarter === q.quarter ? 'db-selected' : undefined}>
              <th scope="row">Q{q.quarter}</th>
              {columns.map((c) => (
                <td key={c.key} className="db-num">
                  <CellLink to={quarterCellPath(scope, q.quarter, c.key)} cell={q.cells[c.key]} />
                </td>
              ))}
              <td className="db-num">
                <CellLink to={closingQuarterPath(scope, { year: scope.year, quarter: q.quarter }, sets)} cell={q.openTotal} />
              </td>
              <td className="db-num db-total">
                <CellLink to={quarterTotalPath(scope, q.quarter, sets)} cell={q.total} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Forecast 탭(슬라이드 9): Forecast 구분별 타일(연간) → Quarter Closing Forecast(누적 막대 + 표) → Selected Quarter → Closing Attention. */
export function ForecastTab({ summary, scope, selectedQuarter, onSelectQuarter }: Props) {
  return (
    <div className="db-stack">
      <ForecastTiles summary={summary} scope={scope} />
      <section className="db-panel" aria-labelledby="db-quarter-heading">
        <h2 id="db-quarter-heading">Quarter Closing Forecast</h2>
        <p className="hint">
          Expected Close가 속한 분기별 Forecast 구분 금액입니다(Lost 제외). 4개 분기를 모두 보이며 아래 Selected Quarter의 분기를 진하게 표시합니다.
        </p>
        <QuarterChart columns={summary.forecast.columns} quarters={summary.quarters} scope={scope} selectedQuarter={selectedQuarter} />
        <QuarterTable summary={summary} scope={scope} selectedQuarter={selectedQuarter} />
      </section>
      <SelectedQuarterSection summary={summary} scope={scope} selectedQuarter={selectedQuarter} onSelect={onSelectQuarter} />
      <ClosingAttention summary={summary} scope={scope} />
    </div>
  )
}
