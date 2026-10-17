/** 날짜·시각 순수 유틸. 달력 날짜는 'YYYY-MM-DD', 시각은 오프셋 포함 ISO 문자열. */

const DAY_MS = 86_400_000

function utcMs(date: string): number {
  const [y, m, d] = date.slice(0, 10).split('-').map(Number)
  if (y === undefined || m === undefined || d === undefined || Number.isNaN(y + m + d)) {
    throw new RangeError(`날짜 형식이 올바르지 않습니다: ${date}`)
  }
  return Date.UTC(y, m - 1, d)
}

function pad(n: number, width = 2): string {
  return String(n).padStart(width, '0')
}

/** ISO 문자열에서 달력 날짜 부분('YYYY-MM-DD')만 꺼낸다(오프셋을 바꾸지 않는다). */
export function datePart(iso: string): string {
  return iso.slice(0, 10)
}

export function addDays(date: string, days: number): string {
  const d = new Date(utcMs(date) + days * DAY_MS)
  return `${pad(d.getUTCFullYear(), 4)}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
}

/** a - b (일수). */
export function daysBetween(a: string, b: string): number {
  return Math.round((utcMs(a) - utcMs(b)) / DAY_MS)
}

/** 'YYYYMMDD'. */
export function compactDate(date: string): string {
  return date.slice(0, 10).replaceAll('-', '')
}

/** 오프셋('+09:00')을 분으로. 형식이 없으면 0. */
export function offsetMinutes(iso: string): number {
  const m = /([+-])(\d{2}):(\d{2})$/.exec(iso)
  if (!m) return 0
  const minutes = Number(m[2]) * 60 + Number(m[3])
  return m[1] === '-' ? -minutes : minutes
}

export function offsetSuffix(minutes: number): string {
  const sign = minutes < 0 ? '-' : '+'
  const abs = Math.abs(minutes)
  return `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
}

/** epoch ms → 주어진 오프셋(분)의 ISO 문자열. */
export function formatWithOffset(ms: number, minutes: number): string {
  const d = new Date(ms + minutes * 60_000)
  const date = `${pad(d.getUTCFullYear(), 4)}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
  return `${date}T${time}${offsetSuffix(minutes)}`
}

/** 두 ISO 시각 중 더 늦은 것. 오프셋이 달라도 시각 기준으로 비교한다. */
export function laterOf(a: string, b: string): string {
  return Date.parse(a) >= Date.parse(b) ? a : b
}

/** 시각 비교용(오름차순). */
export function compareIso(a: string, b: string): number {
  return Date.parse(a) - Date.parse(b)
}
