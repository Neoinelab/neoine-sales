/** 날짜 입력 칸의 글자(yyyy.mm.dd)와 값('YYYY-MM-DD')을 오가는 순수 함수. 브라우저 시간대를 쓰지 않는다. */

export type DateParse =
  | { kind: 'empty' }
  | { kind: 'valid'; iso: string }
  | { kind: 'incomplete' }
  | { kind: 'invalid' }
  | { kind: 'out_of_range' }

const MIN_YEAR = 1900
const MAX_YEAR = 2999
const FIELD_WIDTH = [4, 2, 2]

export const DATE_INCOMPLETE_MESSAGE = '날짜를 yyyymmdd 형식으로 입력하세요.'
export const DATE_INVALID_MESSAGE = '없는 날짜입니다.'
export const DATE_OUT_OF_RANGE_MESSAGE = '1900.01.01부터 2999.12.31 사이로 입력하세요.'

/** 입력할 때마다 칸 글자를 연(4)·월(2)·일(2) 칸에 맞춰 다시 만든다. */
export function formatDateTyping(raw: string): string {
  const fields = ['', '', '']
  let index = 0
  let trailing = false
  for (const ch of raw) {
    if (/\d/.test(ch)) {
      if (index < 3 && (fields[index]?.length ?? 0) >= (FIELD_WIDTH[index] ?? 0)) index += 1
      if (index > 2) continue
      fields[index] = (fields[index] ?? '') + ch
      trailing = false
    } else if (ch === '.' || ch === '-' || ch === '/') {
      if (fields[index] !== '' && !trailing) {
        index += 1
        trailing = true
      }
    }
  }
  const filled = fields.filter((f) => f !== '')
  const text = filled.join('.')
  return trailing && filled.length < 3 && filled.length > 0 ? `${text}.` : text
}

/** blur·Enter 때 `연.월.일`이 모두 있고 연이 4자리면 월·일을 2자리로 채운다. */
export function finalizeDateText(text: string): string {
  const m = /^(\d{4})\.(\d{1,2})\.(\d{1,2})$/.exec(text)
  if (!m) return text
  return `${m[1]}.${(m[2] ?? '').padStart(2, '0')}.${(m[3] ?? '').padStart(2, '0')}`
}

function daysInMonth(year: number, month: number): number {
  if (month === 2) return year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0) ? 29 : 28
  return [4, 6, 9, 11].includes(month) ? 30 : 31
}

export function parseDateText(text: string): DateParse {
  const trimmed = text.trim()
  if (trimmed === '') return { kind: 'empty' }
  const m = /^(\d{4})\.(\d{2})\.(\d{2})$/.exec(trimmed)
  if (!m) return { kind: 'incomplete' }
  const year = Number(m[1])
  const month = Number(m[2])
  const day = Number(m[3])
  if (month < 1 || month > 12 || day < 1 || day > daysInMonth(year, month)) return { kind: 'invalid' }
  if (year < MIN_YEAR || year > MAX_YEAR) return { kind: 'out_of_range' }
  return { kind: 'valid', iso: `${m[1]}-${m[2]}-${m[3]}` }
}

export function isoToDateText(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso)
  return m ? `${m[1]}.${m[2]}.${m[3]}` : iso
}

export function isDateValue(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && parseDateText(isoToDateText(value)).kind === 'valid'
}

export function dateParseError(parsed: DateParse): string | null {
  switch (parsed.kind) {
    case 'incomplete':
      return DATE_INCOMPLETE_MESSAGE
    case 'invalid':
      return DATE_INVALID_MESSAGE
    case 'out_of_range':
      return DATE_OUT_OF_RANGE_MESSAGE
    default:
      return null
  }
}

/** 값('' · 올바른 ISO · 화면 글자 그대로)이 틀렸을 때의 문구. 비었거나 올바르면 null. */
export function dateValueError(value: string): string | null {
  if (value === '') return null
  return dateParseError(parseDateText(isoToDateText(value)))
}

/** 칸 글자가 부모에게 넘길 값: 올바르면 ISO, 비면 '', 그 밖은 글자 그대로. */
export function dateTextToValue(text: string): string {
  const parsed = parseDateText(text)
  if (parsed.kind === 'valid') return parsed.iso
  if (parsed.kind === 'empty') return ''
  return text
}
