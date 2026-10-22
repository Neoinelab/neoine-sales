import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip, type ChartEvent, type ActiveElement } from 'chart.js'
import { formatThousandWon } from '../../shared/model/money'

// `chart.js/auto` 대신 막대 차트에 필요한 요소만 등록한다(번들 크기).
ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

/** Forecast 열 하나에 하나씩 쓰는 색(열 순서대로, 넘치면 되풀이). 밝은 배경과 어두운 배경 모두에서 구분된다. */
export const SERIES_COLORS = ['#94a3b8', '#60a5fa', '#34d399', '#fbbf24', '#f472b6', '#a78bfa', '#fb923c', '#2dd4bf', '#f87171', '#a3e635'] as const

/** 선택하지 않은 막대를 흐리게 하는 투명도(16진 알파). */
export const DIMMED_ALPHA = '55'

/** 캔버스는 CSS 변수를 못 읽으므로 현재 테마의 글자·눈금선 색을 직접 읽는다. 읽지 못하면(테스트 등) 기본 색. */
export function chartTheme(): { text: string; grid: string } {
  const style = typeof document === 'undefined' ? null : getComputedStyle(document.documentElement)
  const read = (name: string, fallback: string) => style?.getPropertyValue(name).trim() || fallback
  return { text: read('--text', '#374151'), grid: read('--line', '#e5e7eb') }
}

/** 금액 축 눈금: 천원 콤마 숫자. */
export function thousandTick(value: string | number): string {
  return formatThousandWon(Number(value))
}

/** 막대 위에서만 손가락 커서. Chart.js의 `onHover`에 그대로 쓴다. */
export function pointerOnBar(event: ChartEvent, elements: ActiveElement[]): void {
  const target = event.native?.target
  if (target instanceof HTMLElement) target.style.cursor = elements.length > 0 ? 'pointer' : 'default'
}
