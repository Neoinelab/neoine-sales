import type { ChartData, ChartOptions } from 'chart.js'
import { Bar } from 'react-chartjs-2'
import { useNavigate } from 'react-router'
import { AMOUNT_LABEL, formatThousandWon } from '../../shared/model/money'
import type { DashboardStatusItem } from '../../shared/model/types'
import { chartTheme, pointerOnBar, SERIES_COLORS, thousandTick } from './chartSetup'
import { useDrillEnabled } from './DrillLink'
import type { ForecastSets } from '../../shared/model/forecastKeys'
import { statusPath, type DashboardScope } from './drillDown'

interface Props {
  items: readonly DashboardStatusItem[]
  scope: DashboardScope
  sets: ForecastSets
}

/**
 * Status별 금액 막대(Lost 제외). 막대 높이는 금액(원), 건수는 축 라벨 `이름 (N건)`에 둔다.
 * 막대를 누르면 표의 행 링크와 같은 곳(Deal 목록)으로 이동한다. 같은 값은 아래 표에도 있다.
 */
export function StatusChart({ items, scope, sets }: Props) {
  const navigate = useNavigate()
  const drillEnabled = useDrillEnabled()
  const theme = chartTheme()
  const data: ChartData<'bar', number[], string> = {
    labels: items.map((i) => `${i.name} (${i.count}건)`),
    datasets: [{ label: AMOUNT_LABEL, data: items.map((i) => i.amount), backgroundColor: SERIES_COLORS[1] }],
  }
  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (_event, elements) => {
      const item = items[elements[0]?.index ?? -1]
      const path = item ? statusPath(scope, item.key, sets) : null
      if (drillEnabled && path) void navigate(path)
    },
    onHover: pointerOnBar,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (context) => `${AMOUNT_LABEL}: ${formatThousandWon(context.parsed.y ?? 0)}` } },
    },
    scales: {
      x: { ticks: { color: theme.text }, grid: { display: false } },
      y: { beginAtZero: true, ticks: { color: theme.text, callback: thousandTick }, grid: { color: theme.grid }, title: { display: true, text: AMOUNT_LABEL, color: theme.text } },
    },
  }
  return (
    <div className="db-chart">
      <Bar data={data} options={options} role="img" aria-label="Status별 Deal 금액(단위:천원) 막대 차트. 같은 값이 아래 표에 있습니다." />
    </div>
  )
}
