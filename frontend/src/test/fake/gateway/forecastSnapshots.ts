/**
 * Forecast 월말 스냅숏 읽기의 Fake. 서버 규칙과 같게 정한다(FC-R36).
 * - 목록은 최근 기준 월부터. 요약은 실시간 요약과 같은 모양(basis 'snapshot', asOf = 생성 시각).
 * - 값은 스냅숏에 저장된 셀이다(현재 Deal·코드가 아니다). 열은 스냅숏에 저장된 코드 목록에서 만들어
 *   (Lost 제외, 저장 order 순) 기간을 바꿔도 같고, 저장 당시 Deal이 없던 코드도 0건 열이며 이름은 저장 당시 이름이다.
 * - 담당자 표시는 지금의 사용자 정보다(퇴사자는 `이름(퇴사)`, 재직자 먼저 → 이름의 문자 코드 순 → id 순).
 * - Vendor 조건은 스냅숏에 없어 422 request-validation, 없는 기준 월·형식이 틀린 기준 월은 404("…없습니다: <기준 월>").
 */

import { userLabel } from '../../../shared/model/period'
import type {
  ForecastCell,
  ForecastColumn,
  ForecastQuery,
  ForecastSnapshotInfo,
  ForecastSummary,
  ForecastSummaryRow,
  UserRef,
} from '../../../shared/model/types'
import { QUARTER_MONTH_EXCLUSIVE, notFound, requestValidation, validation } from '../errors'
import type { ForecastSnapshotCellRecord, ForecastSnapshotRecord } from '../store'
import { requireUser, type MockContext } from './context'
import { userRef } from './views'

/** 서버 순서: 재직자 먼저 → 이름의 문자 코드 순(로캘 비교 아님) → 사용자 id 순. */
export function orderedRows(entries: { ref: UserRef; row: ForecastSummaryRow }[]): ForecastSummaryRow[] {
  const byCode = (a: string, b: string): number => (a < b ? -1 : a > b ? 1 : 0)
  return [...entries]
    .sort(
      (a, b) =>
        Number(a.ref.status === 'resigned') - Number(b.ref.status === 'resigned') || byCode(a.ref.name, b.ref.name) || a.ref.id - b.ref.id,
    )
    .map((entry) => entry.row)
}

const PERIOD_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/
/** 서버 문구: 없는 기준 월과 형식이 틀린 기준 월은 같은 404이고 문구 끝에 보낸 기준 월이 붙는다. */
export const snapshotNotFoundMessage = (period: string): string => `해당 기준 월의 스냅숏이 없습니다: ${period}`

const blankCell = (): ForecastCell => ({ count: 0, amount: 0 })

export function listSnapshots(ctx: MockContext): ForecastSnapshotInfo[] {
  requireUser(ctx)
  return [...(ctx.store.data.forecastSnapshots ?? [])]
    .sort((a, b) => b.period.localeCompare(a.period))
    .map((s) => ({ period: s.period, takenAt: s.takenAt }))
}

function inRange(cell: ForecastSnapshotCellRecord, query: Omit<ForecastQuery, 'vendorId'>): boolean {
  if (cell.revenueYear !== query.year) return false
  if (query.month !== undefined) return cell.revenueMonth === query.month
  if (query.quarter !== undefined) return Math.ceil(cell.revenueMonth / 3) === query.quarter
  return true
}

function find(ctx: MockContext, period: string): ForecastSnapshotRecord {
  const found = PERIOD_PATTERN.test(period) ? (ctx.store.data.forecastSnapshots ?? []).find((s) => s.period === period) : undefined
  if (!found) throw notFound(snapshotNotFoundMessage(period))
  return found
}

export function snapshotSummary(ctx: MockContext, period: string, query: Omit<ForecastQuery, 'vendorId'>): ForecastSummary {
  requireUser(ctx)
  // 서버와 같은 판정 순서: 조건 검증(422)이 기준 월 조회(404)보다 먼저다.
  if ((query as ForecastQuery).vendorId !== undefined) throw requestValidation() // 스냅숏에는 Vendor가 없어 서버가 모르는 키로 거절한다
  if (query.quarter !== undefined && query.month !== undefined) throw validation(QUARTER_MONTH_EXCLUSIVE)
  const snapshot = find(ctx, period)

  const columns: ForecastColumn[] = snapshot.columns
    .filter((c) => c.outcome !== 'lost') // Lost는 열이 아니다
    .sort((a, b) => a.order - b.order)
    .map((c) => ({ key: c.key, name: c.name, outcome: c.outcome === 'won' ? 'won' : 'open', order: c.order }))
  const openKeys = new Set(columns.filter((c) => c.outcome === 'open').map((c) => c.key))
  const blank = (ownerId: number | null, ownerName: string): ForecastSummaryRow => ({
    ownerId,
    ownerName,
    cells: Object.fromEntries(columns.map((c) => [c.key, blankCell()])),
    total: blankCell(),
  })

  const totalRow = blank(null, '합계')
  const byOwner = new Map<number, { ref: UserRef; row: ForecastSummaryRow }>()
  for (const c of snapshot.cells) {
    const target = totalRow.cells[c.forecastKey]
    if (!target || !inRange(c, query)) continue // Lost 등 열에 없는 Forecast와 기간 밖 셀은 제외
    if (query.ownerId !== undefined && c.ownerId !== query.ownerId) continue
    const ref = userRef(ctx.store.data, c.ownerId)
    const entry = byOwner.get(ref.id) ?? { ref, row: blank(ref.id, userLabel(ref)) }
    byOwner.set(ref.id, entry)
    for (const side of [entry.row, totalRow]) {
      const cell = side.cells[c.forecastKey]
      if (cell) {
        cell.count += c.count
        cell.amount += c.amount
      }
      if (openKeys.has(c.forecastKey)) {
        side.total.count += c.count
        side.total.amount += c.amount
      }
    }
  }
  const rows = orderedRows([...byOwner.values()])
  return { basis: 'snapshot', asOf: snapshot.takenAt, snapshotPeriod: snapshot.period, query: { ...query }, columns, rows, totalRow }
}
