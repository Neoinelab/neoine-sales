import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip, type ChartEvent, type ActiveElement } from 'chart.js'
import { formatThousandWon } from '../../shared/model/money'

// `chart.js/auto` 대신 막대 차트에 필요한 요소만 등록한다(번들 크기).
ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend)

export { SERIES_COLORS } from '../../shared/ui/chartTheme'

/** 선택하지 않은 막대를 흐리게 하는 투명도(16진 알파). */
export const DIMMED_ALPHA = '55'

export { chartTheme } from '../../shared/ui/chartTheme'

/** 금액 축 눈금: 천원 콤마 숫자. */
export function thousandTick(value: string | number): string {
  return formatThousandWon(Number(value))
}

/** 막대 위에서만 손가락 커서. Chart.js의 `onHover`에 그대로 쓴다. */
export function pointerOnBar(event: ChartEvent, elements: ActiveElement[]): void {
  const target = event.native?.target
  if (target instanceof HTMLElement) target.style.cursor = elements.length > 0 ? 'pointer' : 'default'
}
