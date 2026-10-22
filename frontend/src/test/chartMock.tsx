import type { ChartData, ChartOptions } from 'chart.js'
import { act } from 'react'
import type { CanvasHTMLAttributes } from 'react'

/**
 * `react-chartjs-2`의 jsdom용 대체(`setup.ts`가 전역으로 `vi.mock`). jsdom에는 canvas가 없어 실제 Chart.js를 만들 수 없다.
 * Bar가 받은 `data`·`options`를 기록하고, 나머지 props(role·aria-label 등)는 `<canvas>`에 그대로 넘긴다.
 * 테스트는 `renderedCharts()`로 마지막 렌더의 props를 읽고 `clickBar`로 `options.onClick`을 직접 부른다.
 */

type BarData = ChartData<'bar', number[], string>
type BarOptions = ChartOptions<'bar'>

export interface RecordedChart {
  data: BarData
  options: BarOptions
  canvasProps: CanvasHTMLAttributes<HTMLCanvasElement>
}

interface BarProps extends CanvasHTMLAttributes<HTMLCanvasElement> {
  data: BarData
  options?: BarOptions
}

let recorded: RecordedChart[] = []

/** 지금까지 렌더된 차트(렌더마다 한 항목, 오래된 순서). */
export function renderedCharts(): readonly RecordedChart[] {
  return recorded
}

/** 가장 최근에 렌더된 차트. 없으면 오류. */
export function lastChart(): RecordedChart {
  const chart = recorded.at(-1)
  if (!chart) throw new Error('렌더된 차트가 없습니다.')
  return chart
}

export function resetCharts(): void {
  recorded = []
}

export function Bar({ data, options, ...canvasProps }: BarProps) {
  recorded.push({ data, options: options ?? {}, canvasProps })
  return <canvas data-testid="mock-bar" {...canvasProps} />
}

/** 막대(또는 누적 막대의 조각) 하나를 누른 것과 같다: Chart.js가 `onClick(event, 활성 요소들, chart)`로 부른다. */
export function clickBar(chart: RecordedChart, hit: { index: number; datasetIndex?: number }): void {
  const onClick = chart.options.onClick
  if (!onClick) throw new Error('차트에 onClick이 없습니다.')
  act(() => {
    onClick(new MouseEvent('click') as never, [{ index: hit.index, datasetIndex: hit.datasetIndex ?? 0 }] as never, {} as never)
  })
}

/** 막대가 없는 곳을 누른 것과 같다(활성 요소 없음). */
export function clickEmptyArea(chart: RecordedChart): void {
  const onClick = chart.options.onClick
  if (!onClick) throw new Error('차트에 onClick이 없습니다.')
  act(() => {
    onClick(new MouseEvent('click') as never, [] as never, {} as never)
  })
}
