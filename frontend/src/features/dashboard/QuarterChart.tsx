import type { ChartData, ChartOptions } from 'chart.js'
import { Bar } from 'react-chartjs-2'
import { useNavigate } from 'react-router'
import { AMOUNT_LABEL, formatThousandWon } from '../../shared/model/money'
import type { DashboardQuarter, ForecastColumn } from '../../shared/model/types'
import { chartTheme, DIMMED_ALPHA, pointerOnBar, SERIES_COLORS, thousandTick } from './chartSetup'
import { useDrillEnabled } from './DrillLink'
import { quarterCellPath, type DashboardScope } from './drillDown'

interface Props {
  columns: readonly ForecastColumn[]
  quarters: readonly DashboardQuarter[]
  scope: DashboardScope
  /** 강조할 분기(Selected Quarter). 나머지 막대는 흐리게 보인다. */
  selectedQuarter: number
}

const colorOf = (index: number): string => SERIES_COLORS[index % SERIES_COLORS.length] ?? SERIES_COLORS[0]

/**
 * 분기별 Closing Forecast 누적 막대. 데이터셋 하나가 Forecast 열 하나(Lost 제외)이고 x축은 Q1~Q4다.
 * Selected Quarter의 막대만 진하게 보인다. 조각을 누르면 그 분기·Forecast의 Deal 목록으로 이동한다.
 */
export function QuarterChart({ columns, quarters, scope, selectedQuarter }: Props) {
  const navigate = useNavigate()
  const drillEnabled = useDrillEnabled()
  const theme = chartTheme()
  const data: ChartData<'bar', number[], string> = {
    labels: quarters.map((q) => `Q${q.quarter}`),
    datasets: columns.map((column, index) => {
      const color = colorOf(index)
      return {
        label: column.name,
        data: quarters.map((q) => q.cells[column.key]?.amount ?? 0),
        backgroundColor: quarters.map((q) => (q.quarter === selectedQuarter ? color : `${color}${DIMMED_ALPHA}`)),
      }
    }),
  }
  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    onClick: (_event, elements) => {
      const hit = elements[0]
      const quarter = quarters[hit?.index ?? -1]
      const column = columns[hit?.datasetIndex ?? -1]
      if (drillEnabled && quarter && column) void navigate(quarterCellPath(scope, quarter.quarter, column.key))
    },
    onHover: pointerOnBar,
    plugins: {
      legend: { position: 'bottom', labels: { color: theme.text } },
      tooltip: { callbacks: { label: (context) => `${context.dataset.label ?? ''}: ${formatThousandWon(context.parsed.y ?? 0)}` } },
    },
    scales: {
      x: { stacked: true, ticks: { color: theme.text }, grid: { display: false } },
      y: { stacked: true, beginAtZero: true, ticks: { color: theme.text, callback: thousandTick }, grid: { color: theme.grid }, title: { display: true, text: AMOUNT_LABEL, color: theme.text } },
    },
  }
  return (
    <div className="db-chart">
      <Bar data={data} options={options} role="img" aria-label="분기별 Forecast 구분 금액(단위:천원) 누적 막대 차트. 같은 값이 아래 표에 있습니다." />
    </div>
  )
}
