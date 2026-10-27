import { formatRelativeTime, formatStamp } from '../../../../shared/format'
import { daysBetween, datePart } from '../../../../shared/model/dates'
import { formatThousandWon } from '../../../../shared/model/money'
import type { ReportCell, ReportResultColumn } from '../../../../shared/model/reportTypes'

/** 표시 전용 포맷 맥락. `now`·`today`는 앱 시계(`useToday`), `totals`는 응답의 합계 행이다. */
export interface FormatContext {
  now: string
  today: string
  totals: readonly ReportCell[] | null
}

const EMPTY = '—'
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'] as const
const MILLION = 1_000_000
const HALF_MILLION = 500_000

const separated = (value: number, maxFraction = 0): string => value.toLocaleString('en-US', { maximumFractionDigits: maxFraction })

const isCount = (column: ReportResultColumn): boolean => column.aggregate === 'count' || column.aggregate === 'count_distinct'

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

function percentShare(value: number, column: ReportResultColumn, totals: FormatContext['totals']): string | null {
  if (column.aggregate !== 'sum' && column.aggregate !== 'count') return null
  const total = totals?.[column.index]
  if (typeof total !== 'number' || total === 0) return null
  return `${tenthsPercent(value, total)}%`
}

/** value/total×100을 소수 1자리로 half-up한다. 정수끼리면 BigInt 정수 연산으로 부동소수 오차를 피한다. */
function tenthsPercent(value: number, total: number): string {
  if (!Number.isInteger(value) || !Number.isInteger(total) || value < 0 || total < 0) return ((value / total) * 100).toFixed(1)
  const v = BigInt(value)
  const t = BigInt(total)
  const tenths = (v * 2000n + t) / (2n * t)
  return `${tenths / 10n}.${tenths % 10n}`
}

function formatNumber(value: number, column: ReportResultColumn, ctx: FormatContext): string {
  if (column.format === 'percent_share') return percentShare(value, column, ctx.totals) ?? separated(value, 2)
  if (isCount(column)) return separated(value)
  switch (column.format) {
    case 'krw_thousand':
      return formatThousandWon(Math.round(value))
    case 'krw_million':
      return separated(Math.floor((Math.round(value) + HALF_MILLION) / MILLION))
    case 'decimal1':
      return value.toLocaleString('en-US', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
    case 'year':
      return String(value)
    default:
      return separated(value, 2)
  }
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
  if (column.format === 'prefix' && column.prefixLength !== null) {
    const chars = Array.from(value)
    return chars.length > column.prefixLength ? `${chars.slice(0, column.prefixLength).join('')}…` : value
  }
  return value
}

/**
 * 결과 셀을 화면 글자로 바꾼다(표시 전용. 서버가 묶은 값 — 연도·분기·월 — 은 그대로 보인다).
 * 날짜·시각은 서버가 쓴 오프셋 그대로의 벽시계를 쓰고, 상대 표기는 앱 시계(`ctx`)로만 계산한다.
 */
export function formatCell(value: ReportCell, column: ReportResultColumn, ctx: FormatContext): string {
  if (value === null) return EMPTY
  return typeof value === 'number' ? formatNumber(value, column, ctx) : formatText(value, column, ctx)
}

/** 긴 글 셀의 title(전체 글). text·code·user 열의 문자열만 갖는다. */
export function cellTitle(value: ReportCell, column: ReportResultColumn): string | undefined {
  if (typeof value !== 'string') return undefined
  return column.valueType === 'text' && (column.type === 'text' || column.type === 'code' || column.type === 'user') ? value : undefined
}

/** 머리글. 금액 포맷은 단위를 덧붙인다(건수 집계는 금액이 아니므로 제외). */
export function columnHeader(column: ReportResultColumn): string {
  if (isCount(column)) return column.label
  if (column.format === 'krw_thousand') return `${column.label} (천원)`
  if (column.format === 'krw_million') return `${column.label} (백만원)`
  return column.label
}

export const isNumericColumn = (column: ReportResultColumn): boolean => column.valueType === 'integer' || column.valueType === 'decimal'
