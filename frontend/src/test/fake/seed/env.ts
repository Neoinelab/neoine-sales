/** 시드 날짜 계산 환경. 모든 시드 날짜는 기준일(today) 대비 상대값이라 언제 열어도 기한초과·미업데이트 Deal이 존재한다. */

import { addDays, offsetMinutes, offsetSuffix } from '../../../shared/model/dates'

export interface SeedEnv {
  /** 기준일 'YYYY-MM-DD'. */
  today: string
  /** 기준 시각의 오프셋 접미사(예: '+09:00'). */
  tz: string
  /** 기준일에서 daysAgo일 전 hour시 정각의 ISO 시각. */
  at(daysAgo: number, hour?: number): string
  /** 기준일에서 offset일 뒤의 달력 날짜(음수 가능). */
  date(offset: number): string
}

export function createSeedEnv(now: string): SeedEnv {
  const today = now.slice(0, 10)
  const tz = offsetSuffix(offsetMinutes(now))
  return {
    today,
    tz,
    at: (daysAgo, hour = 10) => `${addDays(today, -daysAgo)}T${String(hour).padStart(2, '0')}:00:00${tz}`,
    date: (offset) => addDays(today, offset),
  }
}
