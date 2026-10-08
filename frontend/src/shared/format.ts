export function formatAmount(amount: string, currency: string): string {
  const [integer = '0', fraction] = amount.split('.')
  const grouped = integer.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${grouped}${fraction ? `.${fraction}` : ''} ${currency}`
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('ko-KR', { dateStyle: 'medium', timeStyle: 'short' })
}

/** ISO 시각 → <input type="datetime-local"> 값(브라우저 시간대 기준). */
export function toLocalInput(iso: string): string {
  const date = new Date(iso)
  const shifted = new Date(date.getTime() - date.getTimezoneOffset() * 60_000)
  return shifted.toISOString().slice(0, 16)
}

/** <input type="datetime-local"> 값 → 시간대가 있는 ISO 문자열. */
export function fromLocalInput(value: string): string {
  return new Date(value).toISOString()
}

/** 날짜(YYYY-MM-DD) 입력의 하루 시작 시각(브라우저 시간대). */
export function dayStart(date: string, plusDays = 0): string {
  const start = new Date(`${date}T00:00:00`)
  start.setDate(start.getDate() + plusDays)
  return start.toISOString()
}

/** 날짜(YYYY-MM-DD)의 다음 날(YYYY-MM-DD). 시간대와 무관하게 달력 계산만 한다. */
export function nextDay(date: string): string {
  const next = new Date(`${date}T00:00:00Z`)
  next.setUTCDate(next.getUTCDate() + 1)
  return next.toISOString().slice(0, 10)
}
