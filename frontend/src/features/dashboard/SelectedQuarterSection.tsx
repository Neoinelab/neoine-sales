import type { DashboardSummary } from '../../shared/model/types'
import { forecastTilePath, openTotalPath, quarterTotalPath, type DashboardScope } from './drillDown'
import { AmountTile } from './Tiles'

const QUARTERS = [1, 2, 3, 4] as const

interface Props {
  summary: DashboardSummary
  scope: DashboardScope
  selectedQuarter: 1 | 2 | 3 | 4
  onSelect: (quarter: 1 | 2 | 3 | 4) => void
}

/**
 * 하단 Selected Quarter: Q1~Q4 토글 버튼과 선택 분기의 Forecast 구분별 타일(열린 구분 → Open 합계 → Won → 합계).
 * 값은 이미 받은 `summary.quarters`를 쓰므로 버튼을 눌러도 다시 조회하지 않는다. 타일은 그 분기 조건의 Deal 목록으로 간다.
 */
export function SelectedQuarterSection({ summary, scope, selectedQuarter, onSelect }: Props) {
  const quarter = summary.quarters.find((q) => q.quarter === selectedQuarter)
  const zero = { count: 0, amount: 0 }
  const inQuarter: DashboardScope = { ...scope, quarter: selectedQuarter }
  const { columns } = summary.forecast
  return (
    <section className="db-panel" aria-labelledby="db-selected-quarter-heading">
      <h2 id="db-selected-quarter-heading">{`Selected Quarter : Q${selectedQuarter}`}</h2>
      <div className="db-quarter-buttons" role="group" aria-label="Selected Quarter">
        {QUARTERS.map((q) => (
          <button key={q} type="button" aria-pressed={q === selectedQuarter} onClick={() => onSelect(q)}>
            {`Q${q}`}
          </button>
        ))}
      </div>
      <section className="db-tiles" aria-label="Selected Quarter 구분별 금액(단위:천원)">
        {columns
          .filter((c) => c.outcome === 'open')
          .map((c) => (
            <AmountTile key={c.key} to={forecastTilePath(inQuarter, c.key)} title={c.name} cell={quarter?.cells[c.key] ?? zero} />
          ))}
        <AmountTile to={openTotalPath(inQuarter)} title="Open 합계" cell={quarter?.openTotal ?? zero} tone="total" />
        {columns
          .filter((c) => c.outcome === 'won')
          .map((c) => (
            <AmountTile key={c.key} to={forecastTilePath(inQuarter, c.key)} title={`${c.name} (${scope.year} Q${selectedQuarter})`} cell={quarter?.cells[c.key] ?? zero} tone="ok" />
          ))}
        <AmountTile to={quarterTotalPath(inQuarter, selectedQuarter)} title="합계" cell={quarter?.total ?? zero} tone="total" />
      </section>
    </section>
  )
}
