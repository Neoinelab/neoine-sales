import { offsetMinutes } from './model/dates'

/** 시각 뒤에 오프셋(Z 또는 ±HH:MM)이 적힌 ISO 문자열만 시각으로 읽는다. 오프셋이 없으면 브라우저 시간대로 해석되므로 읽지 않는다. */
const WITH_OFFSET = /T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/

/** 오프셋이 적힌 ISO 시각의 벽시계(오프셋만큼 옮긴 UTC 시각). 브라우저 시간대를 쓰지 않는다. 읽을 수 없으면 null. */
function wallClock(iso: string): Date | null {
  if (!WITH_OFFSET.test(iso)) return null
  const wall = new Date(Date.parse(iso) + offsetMinutes(iso) * 60_000)
  return Number.isNaN(wall.getTime()) ? null : wall
}

/** 서버가 준 문자열의 오프셋 기준 표시(예: 2026. 10. 23. 오전 9:30). 브라우저 시간대로 바꾸지 않는다. 읽을 수 없는 값은 원문 그대로. */
export function formatDateTime(iso: string): string {
  const wall = wallClock(iso)
  return wall ? new Intl.DateTimeFormat('ko-KR', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(wall) : iso
}

/** 서버가 준 문자열의 오프셋 기준 'YYYY-MM-DD HH:mm'. 읽을 수 없는 값은 원문 그대로. */
export function formatStamp(iso: string): string {
  const wall = wallClock(iso)
  return wall ? wall.toISOString().slice(0, 16).replace('T', ' ') : iso
}

/** 'YYYY-MM-DD' 또는 ISO 시각에서 날짜 부분(YYYY-MM-DD). 입력에 적힌 달력 날짜를 그대로 쓴다. */
export function formatDate(value: string): string {
  return value.slice(0, 10)
}

/**
 * 상대 시각: 방금 전 / N분 전 / N시간 전 / N일 전(30일 미만), 그 이후는 날짜.
 * `now`는 호출처가 `useToday().now`로 넘긴다. 미래 시각은 '방금 전'.
 */
export function formatRelativeTime(iso: string, now: string): string {
  const diff = new Date(now).getTime() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return '방금 전'
  if (minutes < 60) return `${minutes}분 전`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}시간 전`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}일 전`
  return formatDate(iso)
}

/** 날짜(YYYY-MM-DD)의 다음 날(YYYY-MM-DD). 시간대와 무관하게 달력 계산만 한다. */
export function nextDay(date: string): string {
  const next = new Date(`${date}T00:00:00Z`)
  next.setUTCDate(next.getUTCDate() + 1)
  return next.toISOString().slice(0, 10)
}
