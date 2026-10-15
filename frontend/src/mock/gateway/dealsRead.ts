/** Deal 조회: 목록(필터·정렬·페이지), 상세, 삭제 영향, Vendor/Solution 목록. */

import { DEAL_PAGE_SIZE } from '../../shared/model/constants'
import { compareIso } from '../../shared/model/dates'
import { inPeriod } from '../../shared/model/period'
import type { Deal, DealListQuery, DealRow, Page } from '../../shared/model/types'
import { read, requireUser, type MockContext } from './context'
import { codeSetOf } from './dealChange'
import { dealDetail, dealRow, findDeal } from './views'

function matches(row: DealRow, query: DealListQuery, viewerId: string): boolean {
  if (query.keyword) {
    const needle = query.keyword.trim().toLowerCase()
    const haystack = [row.name, row.customer.company, row.activePartner?.company ?? '', row.code]
    if (!haystack.some((text) => text.toLowerCase().includes(needle))) return false
  }
  if (query.ownerId && row.ownerId !== query.ownerId) return false
  if (query.vendor && row.vendor !== query.vendor) return false
  if (query.solution && row.solution !== query.solution) return false
  if (query.statusKey && row.statusKey !== query.statusKey) return false
  if (query.forecastKey && row.forecastKey !== query.forecastKey) return false
  if (query.year !== undefined && !inPeriod(row.revenueDate, query.year, query.quarter)) return false
  if (query.revenueFrom && row.revenueDate < query.revenueFrom) return false
  if (query.revenueTo && row.revenueDate > query.revenueTo) return false
  if (query.mine && row.ownerId !== viewerId) return false
  for (const [category, labelId] of Object.entries(query.bantLabelIds ?? {})) {
    if (labelId && row.bant[category as keyof typeof row.bant] !== labelId) return false
  }
  return true
}

export function listDeals(ctx: MockContext, query: DealListQuery): Page<DealRow> {
  const viewer = requireUser(ctx)
  const statusOrder = codeSetOf(ctx).statuses.map((c) => c.key)
  const sort = query.sort ?? 'lastUpdatedAt'
  const sign = (query.order ?? 'desc') === 'asc' ? 1 : -1
  const compare = (a: DealRow, b: DealRow): number => {
    switch (sort) {
      case 'name':
        return a.name.localeCompare(b.name, 'ko')
      case 'revenueAmount':
        return a.revenueAmount - b.revenueAmount
      case 'revenueDate':
        return a.revenueDate.localeCompare(b.revenueDate)
      case 'statusKey':
        return statusOrder.indexOf(a.statusKey) - statusOrder.indexOf(b.statusKey)
      default:
        return compareIso(a.lastUpdatedAt, b.lastUpdatedAt)
    }
  }
  const rows = ctx.store.data.deals
    .map((deal) => dealRow(ctx, deal))
    .filter((row) => matches(row, query, viewer.id))
    .sort((a, b) => sign * compare(a, b) || a.code.localeCompare(b.code))
  const offset = query.offset ?? 0
  const limit = query.limit ?? DEAL_PAGE_SIZE
  return { items: rows.slice(offset, offset + limit), total: rows.length, offset, limit }
}

export function dealsReadApi(ctx: MockContext) {
  return {
    list: (query: DealListQuery) => read(ctx, () => listDeals(ctx, query)),
    get: (code: string) =>
      read(ctx, () => {
        requireUser(ctx)
        return dealDetail(ctx, findDeal(ctx.store.data, code))
      }),
    impact: (code: string) =>
      read(ctx, () => {
        requireUser(ctx)
        findDeal(ctx.store.data, code)
        const { history, actions, attachments } = ctx.store.data
        return {
          historyCount: history.filter((h) => h.dealCode === code).length,
          actionCount: actions.filter((a) => a.dealCode === code).length,
          attachmentCount: attachments.filter((a) => a.dealCode === code).length,
        }
      }),
    facets: () =>
      read(ctx, () => {
        requireUser(ctx)
        const distinct = (pick: (d: Deal) => string) =>
          [...new Set(ctx.store.data.deals.map(pick))].sort((a, b) => a.localeCompare(b, 'ko'))
        return { vendors: distinct((d) => d.vendor), solutions: distinct((d) => d.solution) }
      }),
  }
}
