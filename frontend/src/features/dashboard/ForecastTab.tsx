import { DrillLink } from './DrillLink'
import { AMOUNT_LABEL } from '../../shared/model/money'
import type { DashboardQuarter, DashboardSummary, ForecastCell } from '../../shared/model/types'
import { AmountText } from '../../shared/ui/AmountText'
import { forecastSetsOf } from '../../shared/model/forecastKeys'
import { closingQuarterPath, quarterCellPath, quarterTotalPath, type DashboardScope } from './drillDown'
import { QuarterChart } from './QuarterChart'
import { ClosingAttention, ForecastTiles } from './Tiles'

interface Props {
  summary: DashboardSummary
  scope: DashboardScope
}

/** 보이는 분기 행: 활성 탭에서 고른 분기만(scope.quarters, 비면 4개 모두). 오름차순은 서버 응답 순서. */
export function visibleQuarters(summary: DashboardSummary, scope: DashboardScope): DashboardQuarter[] {
  return scope.quarters.length > 0 ? summary.quarters.filter((q) => scope.quarters.includes(q.quarter)) : summary.quarters
}

function CellLink({ to, cell }: { to: string | null; cell: ForecastCell | undefined }) {
  const { count, amount } = cell ?? { count: 0, amount: 0 }
  return (
    <DrillLink to={to}>
      {count}건 · <AmountText amount={amount} />
    </DrillLink>
  )
}

/** 분기 표: 차트와 같은 값을 글자로 보인다. 모든 셀이 Deal 목록 링크다. 보이는 분기 행만 낸다. */
function QuarterTable({ summary, scope, rows }: Pick<Props, 'summary' | 'scope'> & { rows: readonly DashboardQuarter[] }) {
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
          {rows.map((q) => (
            <tr key={q.quarter}>
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

/** Forecast 탭(슬라이드 9): Forecast 구분별 타일(고른 분기 합계) → Quarter Closing Forecast(누적 막대 + 표) → Closing Attention. 타일·차트·표는 고른 분기만 집계한다. */
export function ForecastTab({ summary, scope }: Props) {
  const rows = visibleQuarters(summary, scope)
  return (
    <div className="db-stack">
      <ForecastTiles summary={summary} scope={scope} />
      <section className="db-panel" aria-labelledby="db-quarter-heading">
        <h2 id="db-quarter-heading">Quarter Closing Forecast</h2>
        <p className="hint">
          Expected Close가 속한 분기별 Forecast 구분 금액입니다(Lost 제외). 고른 분기만 보이며, 고르지 않으면 4개 분기를 모두 보입니다.
        </p>
        <QuarterChart columns={summary.forecast.columns} quarters={rows} scope={scope} />
        <QuarterTable summary={summary} scope={scope} rows={rows} />
      </section>
      <ClosingAttention summary={summary} scope={scope} />
    </div>
  )
}
