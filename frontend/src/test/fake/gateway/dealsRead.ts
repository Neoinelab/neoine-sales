/** Deal 조회: 목록(필터·정렬·페이지), 상세, 삭제 영향. */

import { DEAL_PAGE_SIZE } from '../../../shared/model/constants'
import { compareIso, datePart } from '../../../shared/model/dates'
import { inPeriod } from '../../../shared/model/period'
import type { DealListQuery, DealRow, Page } from '../../../shared/model/types'
import { validation } from '../errors'
import { read, requireUser, type MockContext } from './context'
import { codeSetOf } from './dealChange'
import { statusesOf } from './nextActionStatus'
import { updatedPeriods } from './updatedPeriods'
import { dealDetail, dealRow, findDeal } from './views'

function matches(row: DealRow, query: DealListQuery, viewerId: number, thisYear: number): boolean {
  if (query.keyword) {
    const needle = query.keyword.trim().toLowerCase()
    const haystack = [row.name, row.customer.company, row.activePartner?.company ?? '', row.code]
    if (!haystack.some((text) => text.toLowerCase().includes(needle))) return false
  }
  if (query.ownerId && row.ownerId !== query.ownerId) return false
  if (query.vendorId && row.vendor?.id !== query.vendorId) return false
  if (query.solutionId && row.solution?.id !== query.solutionId) return false
  if (query.statusKey && row.statusKey !== query.statusKey) return false
  if (query.forecastKey && row.forecastKey !== query.forecastKey) return false
  // 분기만 있으면 올해(Fake 시계의 업무 날짜 연도)의 그 분기다.
  const year = query.year ?? (query.quarter !== undefined ? thisYear : undefined)
  if (year !== undefined && !inPeriod(row.revenueDate, year, query.quarter)) return false
  // 최종 업데이트(Action 기준 lastUpdatedAt)의 달력 날짜가 양끝 포함 범위 안이어야 한다.
  const updatedDay = datePart(row.lastUpdatedAt)
  if (query.updatedFrom && updatedDay < query.updatedFrom) return false
  if (query.updatedTo && updatedDay > query.updatedTo) return false
  if (query.mine && row.ownerId !== viewerId) return false
  // 기준 행(Next Action이 있는 가장 최근 Action)의 상태로 거른다. Next Action이 없는 Deal은 제외된다.
  if (query.nextActionStatus && !(row.nextAction && statusesOf(query.nextActionStatus).includes(row.nextAction.status))) return false
  for (const [category, labelId] of Object.entries(query.bantLabelIds ?? {})) {
    if (labelId && row.bant[category as keyof typeof row.bant] !== labelId) return false
  }
  return true
}

export function listDeals(ctx: MockContext, query: DealListQuery): Page<DealRow> {
  const viewer = requireUser(ctx)
  if (query.updatedFrom && query.updatedTo && query.updatedFrom > query.updatedTo) {
    throw validation('최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다')
  }
  const thisYear = Number(ctx.clock.today().slice(0, 4))
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
    .filter((row) => matches(row, query, viewer.id, thisYear))
    .sort((a, b) => sign * compare(a, b) || a.code.localeCompare(b.code))
  const offset = query.offset ?? 0
  const limit = query.limit ?? DEAL_PAGE_SIZE
  return { items: rows.slice(offset, offset + limit), total: rows.length, offset, limit }
}

export function dealsReadApi(ctx: MockContext) {
  return {
    list: (query: DealListQuery) => read(ctx, () => listDeals(ctx, query)),
    /** 서버 업무 날짜(Fake 시계)를 기준으로 푼 최종 업데이트 프리셋 범위. 로그인한 누구나 읽는다. */
    updatedPeriods: () =>
      read(ctx, () => {
        requireUser(ctx)
        return updatedPeriods(ctx.clock.today())
      }),
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
  }
}
