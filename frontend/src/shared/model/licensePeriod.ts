export type PeriodUnit = 'month' | 'year'

export const PERIOD_UNIT_LABELS: Record<PeriodUnit, string> = { month: '개월', year: '년' }

const pad = (n: number) => String(n).padStart(2, '0')
const daysIn = (year: number, month: number) => new Date(Date.UTC(year, month, 0)).getUTCDate()

function parts(iso: string): [number, number, number] {
  const [y, m, d] = iso.split('-').map(Number)
  return [y ?? 0, m ?? 1, d ?? 1]
}

/** 'YYYY-MM-DD'에 개월 수를 더한다. 그 달에 같은 날이 없으면 말일로 보정한다. */
export function addMonthsClamped(iso: string, months: number): string {
  const [y, m, d] = parts(iso)
  const index = y * 12 + (m - 1) + months
  const year = Math.floor(index / 12)
  const month = (index % 12) + 1
  return `${year}-${pad(month)}-${pad(Math.min(d, daysIn(year, month)))}`
}

/** 'YYYY-MM-DD'의 다음 날. */
export function nextDayOf(iso: string): string {
  const date = new Date(`${iso}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + 1)
  return date.toISOString().slice(0, 10)
}

/**
 * 라이선스 종료일 = 시작일 + 기간 - 1일.
 * 시작일의 일에서 1을 뺀 값을 (시작 월 + 기간) 달에 두고(그 달에 없으면 말일), 일이 1이면 그 달 1일의 전날(전달 말일)이다.
 */
export function licenseEnd(start: string, amount: number, unit: PeriodUnit): string {
  const [y, m, d] = parts(start)
  const index = y * 12 + (m - 1) + (unit === 'year' ? amount * 12 : amount)
  const year = Math.floor(index / 12)
  const month = (index % 12) + 1
  if (d > 1) return `${year}-${pad(month)}-${pad(Math.min(d - 1, daysIn(year, month)))}`
  const before = new Date(Date.UTC(year, month - 1, 0))
  return before.toISOString().slice(0, 10)
}
