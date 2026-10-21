/**
 * Forecast 월말 스냅숏 읽기(P6 R2)의 Fake. 서버 규칙과 같게 정한다.
 * - 목록은 최근 기준 월부터. 요약은 실시간 요약과 같은 모양(basis 'snapshot', asOf = 생성 시각).
 * - 값은 스냅숏에 저장된 셀이다(현재 Deal·코드가 아니다). 열은 스냅숏의 모든 셀에서 만들어(Lost 제외, order 순)
 *   기간을 바꿔도 같고, 이름은 스냅숏 당시 이름이다.
 * - 담당자 표시는 지금의 사용자 정보다(퇴사자는 `이름(퇴사)`, 재직자 먼저 → 이름 순).
 * - Vendor 조건은 스냅숏에 없어 422, 없는 기준 월·형식이 틀린 기준 월은 404.
 */

import { userLabel } from '../../../shared/model/period'
import type {
  ForecastCell,
  ForecastColumn,
  ForecastQuery,
  ForecastSnapshotInfo,
  ForecastSummary,
  ForecastSummaryRow,
} from '../../../shared/model/types'
import { QUARTER_MONTH_EXCLUSIVE, notFound, validation } from '../errors'
import type { ForecastSnapshotCellRecord, ForecastSnapshotRecord } from '../store'
import { requireUser, type MockContext } from './context'
import { userRef } from './views'

const PERIOD_PATTERN = /^\d{4}-(0[1-9]|1[0-2])$/
export const SNAPSHOT_NOT_FOUND = '해당 기준 월의 스냅숏이 없습니다.'
export const SNAPSHOT_VENDOR_REJECTED = '스냅숏에서는 Vendor 조건을 사용할 수 없습니다.'

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
  if (!found) throw notFound(SNAPSHOT_NOT_FOUND)
  return found
}

export function snapshotSummary(ctx: MockContext, period: string, query: Omit<ForecastQuery, 'vendorId'>): ForecastSummary {
  requireUser(ctx)
  // 서버와 같은 판정 순서: 조건 검증(422)이 기준 월 조회(404)보다 먼저다.
  if ((query as ForecastQuery).vendorId !== undefined) throw validation(SNAPSHOT_VENDOR_REJECTED)
  if (query.quarter !== undefined && query.month !== undefined) throw validation(QUARTER_MONTH_EXCLUSIVE)
  const snapshot = find(ctx, period)

  const byKey = new Map<string, ForecastColumn>()
  for (const c of snapshot.cells) {
    if (c.forecastOutcome === 'lost' || byKey.has(c.forecastKey)) continue // Lost는 열이 아니다
    byKey.set(c.forecastKey, {
      key: c.forecastKey,
      name: c.forecastName,
      outcome: c.forecastOutcome === 'won' ? 'won' : 'open',
      order: c.forecastOrder,
    })
  }
  const columns: ForecastColumn[] = [...byKey.values()].sort((a, b) => a.order - b.order)
  const openKeys = new Set(columns.filter((c) => c.outcome === 'open').map((c) => c.key))
  const blank = (ownerId: number | null, ownerName: string): ForecastSummaryRow => ({
    ownerId,
    ownerName,
    cells: Object.fromEntries(columns.map((c) => [c.key, blankCell()])),
    total: blankCell(),
  })

  const totalRow = blank(null, '합계')
  const byOwner = new Map<number, ForecastSummaryRow>()
  for (const c of snapshot.cells) {
    const target = totalRow.cells[c.forecastKey]
    if (!target || !inRange(c, query)) continue // Lost 등 열에 없는 Forecast와 기간 밖 셀은 제외
    if (query.ownerId !== undefined && c.ownerId !== query.ownerId) continue
    const owner = userRef(ctx.store.data, c.ownerId)
    const row = byOwner.get(owner.id) ?? blank(owner.id, userLabel(owner))
    byOwner.set(owner.id, row)
    for (const side of [row, totalRow]) {
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
  const rows = [...byOwner.values()].sort(
    (a, b) => Number(a.ownerName.endsWith('(퇴사)')) - Number(b.ownerName.endsWith('(퇴사)')) || a.ownerName.localeCompare(b.ownerName, 'ko'),
  )
  return { basis: 'snapshot', asOf: snapshot.takenAt, snapshotPeriod: snapshot.period, query: { ...query }, columns, rows, totalRow }
}
