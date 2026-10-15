import type { ForecastSummary } from '../../shared/model/types'
import { AmountText } from '../../shared/ui/AmountText'
import { periodLabel, type ForecastFilters } from './forecastParams'

/** 선택한 기간(연도/Quarter)의 요약 카드: Open 합계(Won·Lost 제외)와 Won(별도). */
export function QuarterCards({ summary, filters }: { summary: ForecastSummary; filters: ForecastFilters }) {
  const period = periodLabel(filters)
  const won = summary.columns.filter((c) => c.outcome === 'won').reduce(
    (sum, c) => {
      const cell = summary.totalRow.cells[c.key]
      return { count: sum.count + (cell?.count ?? 0), amount: sum.amount + (cell?.amount ?? 0) }
    },
    { count: 0, amount: 0 },
  )
  const open = summary.totalRow.total
  return (
    <section className="fc-cards" aria-label={`${period} 요약`}>
      <div className="fc-card">
        <h2>Open 합계</h2>
        <p className="fc-card-value">
          <AmountText amount={open.amount} />
        </p>
        <p className="hint">
          {period} · {open.count}건
        </p>
      </div>
      <div className="fc-card fc-card-won">
        <h2>Won (별도)</h2>
        <p className="fc-card-value">
          <AmountText amount={won.amount} />
        </p>
        <p className="hint">
          {period} · {won.count}건
        </p>
      </div>
    </section>
  )
}
