import { DrillLink } from './DrillLink'
import { AMOUNT_LABEL } from '../../shared/model/money'
import type { DashboardSummary } from '../../shared/model/types'
import { AmountText } from '../../shared/ui/AmountText'
import { statusPath, statusTotalPath, type DashboardScope } from './drillDown'
import { StatusChart } from './StatusChart'
import { ForecastTiles, StatusAttention } from './Tiles'

interface Props {
  summary: DashboardSummary
  scope: DashboardScope
}

/** Status 표: 차트와 같은 값을 글자로 보인다. 각 행의 이름이 Deal 목록 링크다. */
function StatusTable({ summary, scope }: Props) {
  const { items, total } = summary.statuses
  return (
    <div className="db-scroll">
      <table className="db-table" aria-label="Status별 건수와 금액">
        <thead>
          <tr>
            <th scope="col">Status</th>
            <th scope="col" className="db-num">
              건수
            </th>
            <th scope="col" className="db-num">
              {AMOUNT_LABEL}
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.key}>
              <th scope="row">
                <DrillLink to={statusPath(scope, item.key)}>{item.name}</DrillLink>
              </th>
              <td className="db-num">{item.count}건</td>
              <td className="db-num">
                <AmountText amount={item.amount} />
              </td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">
              <DrillLink to={statusTotalPath(scope)}>합계</DrillLink>
            </th>
            <td className="db-num">{total.count}건</td>
            <td className="db-num">
              <AmountText amount={total.amount} />
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

/** Status 탭(슬라이드 7): Forecast 구분별 타일 → 전체 Status Pipeline(막대 + 표) → 주의 필요 Deal. */
export function StatusTab({ summary, scope }: Props) {
  return (
    <div className="db-stack">
      <ForecastTiles summary={summary} scope={scope} />
      <section className="db-panel" aria-labelledby="db-status-heading">
        <h2 id="db-status-heading">전체 Status Pipeline</h2>
        <p className="hint">Lost를 제외한 Deal입니다. 막대나 표의 이름을 누르면 해당 Deal 목록으로 이동합니다.</p>
        <StatusChart items={summary.statuses.items} scope={scope} />
        <StatusTable summary={summary} scope={scope} />
      </section>
      <StatusAttention summary={summary} scope={scope} />
    </div>
  )
}
