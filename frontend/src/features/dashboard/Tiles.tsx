import { DrillLink } from './DrillLink'
import type { DashboardSummary, ForecastCell } from '../../shared/model/types'
import { AmountText } from '../../shared/ui/AmountText'
import {
  closingMonthPath,
  closingQuarterPath,
  forecastSetsOf,
  forecastTilePath,
  openTotalPath,
  overduePath,
  stalePath,
  type DashboardScope,
} from './drillDown'

interface TileProps {
  to: string | null
  title: string
  cell: ForecastCell
  tone?: 'ok' | 'total'
}

/** 건수와 금액(천원) 타일. 타일 전체가 Deal 목록으로 가는 링크다. */
export function AmountTile({ to, title, cell, tone }: TileProps) {
  return (
    <DrillLink to={to} className={tone ? `db-tile db-tile-${tone}` : 'db-tile'}>
      <span className="db-tile-title">{title}</span>
      <span className="db-tile-count">{cell.count}건</span>
      <span className="db-tile-value">
        <AmountText amount={cell.amount} />
      </span>
    </DrillLink>
  )
}

const periodText = (period: DashboardSummary['period']): string => (period.quarter ? `${period.year} Q${period.quarter}` : String(period.year))

interface Props {
  summary: DashboardSummary
  scope: DashboardScope
}

/**
 * Forecast 구분별 타일(Lost 제외) + Open 합계. 두 탭이 같이 쓴다.
 * Open 타일은 코드 순서대로, 이어서 Open 합계, 마지막이 Won(제목에 선택 기간). admin이 추가·이름을 바꾼 코드도 서버가 준 열을 그대로 따른다.
 */
export function ForecastTiles({ summary, scope }: Props) {
  const { columns, cells, openTotal } = summary.forecast
  const zero = { count: 0, amount: 0 }
  const sets = forecastSetsOf(columns)
  return (
    <section className="db-tiles" aria-label="Forecast 구분별 금액(단위:천원)">
      {columns
        .filter((c) => c.outcome === 'open')
        .map((c) => (
          <AmountTile key={c.key} to={forecastTilePath(scope, c.key)} title={c.name} cell={cells[c.key] ?? zero} />
        ))}
      <AmountTile to={openTotalPath(scope, sets)} title="Open 합계" cell={openTotal} tone="total" />
      {columns
        .filter((c) => c.outcome === 'won')
        .map((c) => (
          <AmountTile key={c.key} to={forecastTilePath(scope, c.key)} title={`${c.name} (${periodText(summary.period)})`} cell={cells[c.key] ?? zero} tone="ok" />
        ))}
    </section>
  )
}

function CountTile({ to, title, count }: { to: string | null; title: string; count: number }) {
  return (
    <DrillLink to={to} className="db-tile db-tile-attention">
      <span className="db-tile-title">{title}</span>
      <span className="db-tile-count">{count}건</span>
    </DrillLink>
  )
}

/** 주의 필요 Deal 타일의 "N일 이상 미업데이트" 문구(N은 Admin이 정한 경고 기준). */
const staleTitle = (days: number): string => `${days}일 이상 미업데이트`

const quarterTitle = (q: { year: number; quarter: number }): string => `이번 분기(${q.year} Q${q.quarter}) Expected Close`

/** Status 탭: 기한초과 / 미업데이트 / 이번 분기 Expected Close. 담당자·Vendor만 적용하고 기간은 적용하지 않는다. */
export function StatusAttention({ summary, scope }: Props) {
  const { attention } = summary
  const sets = forecastSetsOf(summary.forecast.columns)
  return (
    <section className="db-tiles" aria-label="주의 필요 Deal">
      <CountTile to={overduePath(scope)} title="기한초과" count={attention.overdue} />
      <CountTile to={stalePath(scope)} title={staleTitle(attention.staleDays)} count={attention.stale} />
      <CountTile to={closingQuarterPath(scope, attention.closingThisQuarter, sets)} title={quarterTitle(attention.closingThisQuarter)} count={attention.closingThisQuarter.count} />
    </section>
  )
}

/** Forecast 탭: 이번 달 / 이번 분기 Expected Close, 미업데이트. */
export function ClosingAttention({ summary, scope }: Props) {
  const { attention } = summary
  const sets = forecastSetsOf(summary.forecast.columns)
  return (
    <section className="db-tiles" aria-label="Closing Attention">
      <CountTile
        to={closingMonthPath(scope, attention.closingThisMonth, sets)}
        title={`이번 달(${attention.closingThisMonth.month}월) Expected Close`}
        count={attention.closingThisMonth.count}
      />
      <CountTile to={closingQuarterPath(scope, attention.closingThisQuarter, sets)} title={quarterTitle(attention.closingThisQuarter)} count={attention.closingThisQuarter.count} />
      <CountTile to={stalePath(scope)} title={staleTitle(attention.staleDays)} count={attention.stale} />
    </section>
  )
}
