/** 최종 업데이트 기간 프리셋을 오늘 기준 날짜 범위로 푼다(서버 규칙의 테스트 전용 TS 구현). */

import { addDays } from '../../../shared/model/dates'
import type { UpcomingPeriodKey, UpdatedPeriodKey, UpdatedPeriods } from '../../../shared/model/types'

const MONTHS: Record<Exclude<UpdatedPeriodKey, '2w'>, number> = { '1m': 1, '2m': 2, '3m': 3, '6m': 6 }
const UPCOMING_MONTHS: Record<UpcomingPeriodKey, number> = { '1m': 1, '2m': 2 }
const UPCOMING_ORDER: readonly UpcomingPeriodKey[] = ['1m', '2m']
const ORDER: readonly UpdatedPeriodKey[] = ['2w', '1m', '2m', '3m', '6m']

/** n개월 전 같은 날. 그 달에 그 날이 없으면 그 달의 말일이다. */
export function monthsBefore(day: string, months: number): string {
  const [y, m, d] = day.split('-').map(Number) as [number, number, number]
  const index = y * 12 + (m - 1) - months
  const year = Math.floor(index / 12)
  const month = (index % 12) + 1
  const last = new Date(Date.UTC(year, month, 0)).getUTCDate()
  return `${String(year).padStart(4, '0')}-${String(month).padStart(2, '0')}-${String(Math.min(d, last)).padStart(2, '0')}`
}

/** n개월 뒤 같은 날. 그 달에 그 날이 없으면 그 달의 말일이다(서버 `months_after`와 같은 규칙). */
export function monthsAfter(day: string, months: number): string {
  return monthsBefore(day, -months)
}

export function updatedPeriods(today: string): UpdatedPeriods {
  return {
    today,
    periods: ORDER.map((key) => ({
      key,
      from: key === '2w' ? addDays(today, -14) : monthsBefore(today, MONTHS[key]),
      to: today,
    })),
    upcoming: UPCOMING_ORDER.map((key) => ({ key, from: today, to: monthsAfter(today, UPCOMING_MONTHS[key]) })),
  }
}
