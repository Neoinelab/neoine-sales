import type { UpcomingPeriodKey, UpdatedPeriodKey, UpdatedPeriods } from './types'

const KEYS: readonly string[] = ['2w', '1m', '2m', '3m', '6m']

export function isPeriodKey(value: string): value is UpdatedPeriodKey {
  return KEYS.includes(value)
}

const UPCOMING_KEYS: readonly string[] = ['1m', '2m']

export function isUpcomingKey(value: string): value is UpcomingPeriodKey {
  return UPCOMING_KEYS.includes(value)
}

/** 'YYYY-MM-DD' 형식의 실제 달력 날짜인지(2026-02-30 같은 값은 아니다). */
export function isCalendarDate(value: string | undefined): value is string {
  if (value === undefined || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value
}

/**
 * URL의 최종 업데이트 날짜가 서버 프리셋과 정확히 같으면 그 키, 둘 다 없으면 ''(전체), 그 밖은 'custom'.
 * 프리셋을 아직 모르면(로딩·오류) 날짜가 있는 한 'custom'이다. 날짜는 서버가 준 값과 비교만 한다.
 */
export function selectedUpdatedPeriod(
  from: string | undefined,
  to: string | undefined,
  periods: UpdatedPeriods['periods'] | undefined,
): UpdatedPeriodKey | '' | 'custom' {
  if (!from && !to) return ''
  const match = periods?.find((p) => p.from === from && p.to === to)
  return match ? match.key : 'custom'
}
