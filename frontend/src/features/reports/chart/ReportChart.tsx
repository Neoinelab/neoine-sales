import ChartDataLabels from 'chartjs-plugin-datalabels'
import { Chart } from 'react-chartjs-2'
import type { BuiltChart } from './buildChart'
import './chartRegistry'

// 인스턴스 플러그인(전역 등록 아님: Dashboard 차트에는 영향이 없다). 켜고 끄는 것은 옵션 `datalabels.display`가 한다.
const PLUGINS = [ChartDataLabels]

interface ReportChartProps {
  built: BuiltChart
  title: string
  /** 종류·보조 축처럼 데이터셋 모양이 바뀌면 차트를 새로 만든다. */
  shapeKey: string
}

/** Chart.js 그림. 값은 결과 표에 같은 것이 있으므로 접근성 이름에 그 사실을 적는다. */
export function ReportChart({ built, title, shapeKey }: ReportChartProps) {
  const label = `${title === '' ? '' : `${title}. `}${built.description}. 같은 값이 결과 표에 있습니다`
  return (
    <div className="report-chart-canvas">
      <Chart key={shapeKey} type={built.type} data={built.data} options={built.options} plugins={PLUGINS} role="img" aria-label={label} />
    </div>
  )
}
