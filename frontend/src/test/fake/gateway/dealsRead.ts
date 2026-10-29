/** Deal 조회: 목록(필터·정렬·페이지), 상세, 삭제 영향. */

import { DEAL_PAGE_SIZE } from '../../../shared/model/constants'
import { compareIso, datePart } from '../../../shared/model/dates'
import type { DealListQuery, DealRow, DealSortKey, ForecastOutcome, Page } from '../../../shared/model/types'
import { QUARTER_MONTH_EXCLUSIVE, validation } from '../errors'
import { read, requireUser, type MockContext } from './context'
import { codeSetOf } from './dealChange'
import { normalizedQuarters, quarterOfMonth } from './quarters'
import { statusesOf } from './nextActionStatus'
import { updatedPeriods } from './updatedPeriods'
import { dealDetail, dealRow, findDeal } from './views'

/** 서버 `MAX_LIMIT`와 같은 값. */
export const MAX_PAGE_SIZE = 200

function matches(
  row: DealRow,
  query: DealListQuery,
  viewerId: number,
  thisYear: number,
  outcomeOf: ReadonlyMap<string, ForecastOutcome>,
): boolean {
  if (query.keyword) {
    const needle = query.keyword.trim().toLowerCase()
    const haystack = [row.name, row.customer.company, row.activePartner?.company ?? '', row.code]
    if (!haystack.some((text) => text.toLowerCase().includes(needle))) return false
  }
  if (query.ownerId && row.ownerId !== query.ownerId) return false
  if (query.vendorId && row.vendor?.id !== query.vendorId) return false
  const solution = query.solution?.trim().toLowerCase()
  if (solution && !row.solution.toLowerCase().includes(solution)) return false
  if (query.statusKey && row.statusKey !== query.statusKey) return false
  if (query.forecastKeys?.length && !query.forecastKeys.includes(row.forecastKey)) return false
  // Forecast 코드의 outcome 기준(not_lost = open + won). 코드를 모르는 key는 open으로 본다.
  if (query.forecastOutcome) {
    const outcome = outcomeOf.get(row.forecastKey) ?? 'open'
    const allowed = query.forecastOutcome === 'not_lost' ? ['open', 'won'] : [query.forecastOutcome]
    if (!allowed.includes(outcome)) return false
  }
  // 분기만 있으면 올해(Fake 시계의 업무 날짜 연도)의 그 분기다.
  const quarters = normalizedQuarters(query.quarters)
  const year = query.year ?? (quarters !== undefined || query.month !== undefined ? thisYear : undefined)
  if (year !== undefined && Number(row.revenueDate.slice(0, 4)) !== year) return false
  // 고른 분기 중 하나(OR). 없음·넷 다는 조건 없음이다.
  if (quarters !== undefined && !quarters.includes(quarterOfMonth(Number(row.revenueDate.slice(5, 7))))) return false
  // 월은 분기와 함께 쓸 수 없다(listDeals가 먼저 거절한다). 그 달의 Deal만 남긴다.
  if (query.month !== undefined && Number(row.revenueDate.slice(5, 7)) !== query.month) return false
  // 최종 업데이트(Action 기준 lastUpdatedAt)의 달력 날짜가 양끝 포함 범위 안이어야 한다.
  const updatedDay = datePart(row.lastUpdatedAt)
  if (query.updatedFrom && updatedDay < query.updatedFrom) return false
  if (query.updatedTo && updatedDay > query.updatedTo) return false
  if (query.mine && row.ownerId !== viewerId) return false
  // 기준 행(Next Action이 있는 가장 최근 Action)의 상태로 거른다. Next Action이 없는 Deal은 제외된다.
  if (query.nextActionStatus && !(row.nextAction && statusesOf(query.nextActionStatus).includes(row.nextAction.status))) return false
  // 기한초과·미업데이트: 이미 계산된 row.risk(종결 Deal은 null)로 판정한다. 둘 다 켜면 어느 하나라도 해당(OR).
  if (query.overdue || query.stale) {
    const overdue = row.risk === 'overdue' || row.risk === 'overdue_stale'
    const stale = row.risk === 'stale' || row.risk === 'overdue_stale'
    if (!((query.overdue && overdue) || (query.stale && stale))) return false
  }
  return true
}

/** 서버 정렬 규칙: 텍스트는 소문자 기준(코드 포인트 순). */
function compareText(a: string, b: string): number {
  const x = a.toLowerCase()
  const y = b.toLowerCase()
  return x < y ? -1 : x > y ? 1 : 0
}

/** 값이 없는 행(활성 파트너·Vendor 없음)은 방향과 무관하게 맨 뒤에 둔다. */
function isAbsent(row: DealRow, sort: DealSortKey): boolean {
  if (sort === 'partner') return row.activePartner === null
  if (sort === 'vendor') return row.vendor === null
  return false
}

export function listDeals(ctx: MockContext, query: DealListQuery): Page<DealRow> {
  const viewer = requireUser(ctx)
  if (query.updatedFrom && query.updatedTo && query.updatedFrom > query.updatedTo) {
    throw validation('최종 업데이트 기간의 시작은 끝보다 늦을 수 없습니다')
  }
  if (normalizedQuarters(query.quarters) !== undefined && query.month !== undefined) throw validation(QUARTER_MONTH_EXCLUSIVE)
  // 서버 한도: 한 번에 최대 200건(그 이상은 422).
  if ((query.limit ?? 0) > MAX_PAGE_SIZE) throw validation(`limit은 ${MAX_PAGE_SIZE} 이하여야 합니다.`)
  const thisYear = Number(ctx.clock.today().slice(0, 4))
  const codes = codeSetOf(ctx)
  const statusOrder = codes.statuses.map((c) => c.key)
  const forecastOrder = codes.forecasts.map((c) => c.key)
  const outcomeOf = new Map(codes.forecasts.map((c) => [c.key, c.outcome]))
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
      case 'forecastKey':
        return forecastOrder.indexOf(a.forecastKey) - forecastOrder.indexOf(b.forecastKey)
      case 'owner':
        return compareText(a.owner.name, b.owner.name)
      case 'customer':
        return compareText(a.customer.company, b.customer.company)
      case 'partner':
        return compareText(a.activePartner?.company ?? '', b.activePartner?.company ?? '')
      case 'vendor':
        return compareText(a.vendor?.name ?? '', b.vendor?.name ?? '')
      default:
        return compareIso(a.lastUpdatedAt, b.lastUpdatedAt)
    }
  }
  const rows = ctx.store.data.deals
    .map((deal) => dealRow(ctx, deal))
    .filter((row) => matches(row, query, viewer.id, thisYear, outcomeOf))
    .sort((a, b) => {
      const absentA = isAbsent(a, sort)
      const absentB = isAbsent(b, sort)
      if (absentA !== absentB) return absentA ? 1 : -1
      return (absentA ? 0 : sign * compare(a, b)) || a.code.localeCompare(b.code)
    })
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
    /** 모든 Deal의 Expected Close 중 가장 이른 연도(서버 `earliest_revenue_year`). Deal이 없으면 null. 로그인한 누구나 읽는다. */
    years: () =>
      read(ctx, () => {
        requireUser(ctx)
        const years = ctx.store.data.deals.map((d) => Number(d.revenueDate.slice(0, 4)))
        return { earliestYear: years.length === 0 ? null : Math.min(...years) }
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
          partnerMeetingCount: (ctx.store.data.partnerMeetings ?? []).filter((m) => m.dealCode === code).length,
        }
      }),
  }
}
