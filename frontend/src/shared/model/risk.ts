/** Risk(기한초과/미업데이트) 판정 순수 함수(A-0 계약, 구현은 A-1). 계획 6.3, R03/R04. */

import { FORECAST_LOST, FORECAST_WON, STALE_DAYS } from './constants'
import { datePart, daysBetween } from './dates'
import type { Risk } from './types'

export interface RiskInput {
  forecastKey: string
  /** 가장 최근 Action의 Due Date. Action이 없으면 null(기한초과 아님). */
  dueDate: string | null
  /** DealRow.lastUpdatedAt(ISO). */
  lastUpdatedAt: string
}

/**
 * 규칙
 * - Forecast가 종결(`won`/`lost`)이면 항상 null.
 * - 기한초과: dueDate < 오늘(달력 날짜 비교). dueDate === 오늘은 기한초과 아님.
 * - 미업데이트: 오늘 - lastUpdatedAt의 달력 일수 >= 14(`STALE_DAYS`). 13일째는 정상, 14일째부터 stale.
 * - 둘 다면 'overdue_stale'.
 * `now`는 오프셋 포함 ISO 문자열이며 '오늘'은 그 문자열이 나타내는 현지 달력 날짜다(clock.ts의 now()).
 */
export function computeRisk(input: RiskInput, now: string): Risk {
  if (isClosedForecast(input.forecastKey)) return null
  const today = datePart(now)
  const overdue = input.dueDate !== null && input.dueDate < today
  const stale = daysBetween(today, datePart(input.lastUpdatedAt)) >= STALE_DAYS
  if (overdue && stale) return 'overdue_stale'
  if (overdue) return 'overdue'
  return stale ? 'stale' : null
}

/** 종결(Won·Lost) Forecast인지. key 기준. */
export function isClosedForecast(forecastKey: string): boolean {
  return forecastKey === FORECAST_WON || forecastKey === FORECAST_LOST
}
