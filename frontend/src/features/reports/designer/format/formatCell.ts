import { formatRelativeTime, formatStamp } from '../../../../shared/format'
import { daysBetween, datePart } from '../../../../shared/model/dates'
import { formatThousandWon } from '../../../../shared/model/money'
import type { ReportCell, ReportResultColumn } from '../../../../shared/model/reportTypes'

/** 표시 전용 포맷 맥락. `now`·`today`는 앱 시계(`useToday`)다. */
export interface FormatContext {
  now: string
  today: string
}

const EMPTY = '—'
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'] as const

const separated = (value: number): string => value.toLocaleString('en-US', { maximumFractionDigits: 0 })

const isCount = (column: ReportResultColumn): boolean => column.aggregate === 'count' || column.aggregate === 'count_distinct'

/** 천원 단위로 보이는 열: 단위가 천원인 필드(금액)이고 건수 집계가 아닌 열. 머리글·표·차트가 이 판정 하나를 쓴다. */
export const isThousandWonColumn = (column: ReportResultColumn): boolean => column.unit === 'krw_thousand' && !isCount(column)

/** 'YYYY-MM-DD'의 요일(달력 계산만 한다. 브라우저 시간대를 쓰지 않는다). */
function weekdayOf(date: string): string {
  const [y, m, d] = date.slice(0, 10).split('-').map(Number)
  if (y === undefined || m === undefined || d === undefined) return ''
  return WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()] ?? ''
}

function relativeDay(date: string, today: string): string {
  const diff = daysBetween(date, today)
  if (diff === 0) return '오늘'
  return diff < 0 ? `${-diff}일 전` : `${diff}일 후`
}

function formatNumber(value: number, column: ReportResultColumn): string {
  if (isCount(column)) return separated(value)
  if (column.format === 'year') return String(value)
  if (isThousandWonColumn(column)) return formatThousandWon(Math.round(value))
  return separated(value)
}

function formatText(value: string, column: ReportResultColumn, ctx: FormatContext): string {
  if (column.valueType === 'date') {
    if (column.format === 'weekday') return `${value} (${weekdayOf(value)})`
    if (column.format === 'relative') return relativeDay(value, ctx.today)
    return value
  }
  if (column.valueType === 'datetime') {
    if (column.format === 'weekday') return `${datePart(value)} (${weekdayOf(value)})`
    if (column.format === 'relative') return formatRelativeTime(value, ctx.now)
    if (column.format === 'ymd') return datePart(value)
    return formatStamp(value)
  }
  return value
}

/**
 * 결과 셀을 화면 글자로 바꾼다(표시 전용. 서버가 묶은 값 — 연도·분기·월 — 은 그대로 보인다).
 * 날짜·시각은 서버가 쓴 오프셋 그대로의 벽시계를 쓰고, 상대 표기는 앱 시계(`ctx`)로만 계산한다.
 */
export function formatCell(value: ReportCell, column: ReportResultColumn, ctx: FormatContext): string {
  if (value === null) return EMPTY
  return typeof value === 'number' ? formatNumber(value, column) : formatText(value, column, ctx)
}

/** 글자를 코드 포인트 기준 앞 n자만 남기고 넘으면 `…`을 붙인다(n이 없으면 그대로). */
export function truncateLabel(text: string, n: number | null): string {
  if (n === null) return text
  const chars = Array.from(text)
  return chars.length > n ? `${chars.slice(0, n).join('')}…` : text
}

/** 화면에 보이는 글자: 포맷한 결과 문자열에 앞 N자 보기를 적용한다(빈 값 "—"은 자르지 않는다). 합계 행·툴팁은 `formatCell`을 쓴다. */
export function formatShownCell(value: ReportCell, column: ReportResultColumn, ctx: FormatContext): string {
  const text = formatCell(value, column, ctx)
  return value === null ? text : truncateLabel(text, column.prefixLength)
}

/** 셀의 title(전체 글). 잘렸으면 포맷한 전체 값, 아니면 text·code·user 열의 문자열만 갖는다. */
export function cellTitle(value: ReportCell, column: ReportResultColumn, ctx: FormatContext): string | undefined {
  if (value === null) return undefined
  const full = formatCell(value, column, ctx)
  if (formatShownCell(value, column, ctx) !== full) return full
  if (typeof value !== 'string') return undefined
  return column.valueType === 'text' && (column.type === 'text' || column.type === 'code' || column.type === 'user') ? value : undefined
}

/** 머리글. 천원 단위 열은 단위를 덧붙인다. */
export function columnHeader(column: ReportResultColumn): string {
  return isThousandWonColumn(column) ? `${column.label} (천원)` : column.label
}

export const isNumericColumn = (column: ReportResultColumn): boolean => column.valueType === 'integer' || column.valueType === 'decimal'
