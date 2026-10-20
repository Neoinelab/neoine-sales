import { api } from '../../shared/api/client'
import type { DealListQuery } from '../../shared/model/types'
import type { DealsGateway } from '../types'
import { toNextActionStatusParam } from './mappers/nextActionStatus'
import { toCoChange, toChangeBody, toCreateBody, toDealDetail, toDealRow, toPatchBody } from './mappers/deal'
import { unwrap, unwrapVoid } from './request'

const SORT = {
  name: 'name',
  revenueAmount: 'revenue_amount',
  revenueDate: 'revenue_date',
  lastUpdatedAt: 'last_updated_at',
  statusKey: 'status',
} as const

/** 지정하지 않은 조건은 보내지 않는다(서버 기본값을 쓴다). mine=false도 보내지 않는다. */
function toListParams(q: DealListQuery) {
  return {
    ...(q.keyword ? { keyword: q.keyword } : {}),
    ...(q.ownerId ? { owner_user_id: q.ownerId } : {}),
    ...(q.vendorId ? { vendor_id: q.vendorId } : {}),
    ...(q.solutionId ? { solution_id: q.solutionId } : {}),
    ...(q.statusKey ? { status_key: q.statusKey } : {}),
    ...(q.forecastKey ? { forecast_key: q.forecastKey } : {}),
    ...(q.year !== undefined ? { year: q.year } : {}),
    ...(q.quarter !== undefined ? { quarter: q.quarter } : {}),
    ...(q.revenueFrom ? { revenue_from: q.revenueFrom } : {}),
    ...(q.revenueTo ? { revenue_to: q.revenueTo } : {}),
    ...(q.bantLabelIds?.budget ? { bant_budget: q.bantLabelIds.budget } : {}),
    ...(q.bantLabelIds?.authority ? { bant_authority: q.bantLabelIds.authority } : {}),
    ...(q.bantLabelIds?.need ? { bant_need: q.bantLabelIds.need } : {}),
    ...(q.bantLabelIds?.timeline ? { bant_timeline: q.bantLabelIds.timeline } : {}),
    ...(q.mine ? { mine: true } : {}),
    ...(q.nextActionStatus ? { next_action_status: toNextActionStatusParam(q.nextActionStatus) } : {}),
    ...(q.sort ? { sort: SORT[q.sort] } : {}),
    ...(q.order ? { order: q.order } : {}),
    ...(q.offset !== undefined ? { offset: q.offset } : {}),
    ...(q.limit !== undefined ? { limit: q.limit } : {}),
  }
}

export function createDealsHttp(): DealsGateway {
  const path = (code: string) => ({ params: { path: { code } } })
  return {
    list: async (query) => {
      const page = await unwrap(api.GET('/api/v1/deals', { params: { query: toListParams(query) } }))
      return { items: page.items.map(toDealRow), total: page.total, offset: page.offset, limit: page.limit }
    },
    get: async (code) => toDealDetail(await unwrap(api.GET('/api/v1/deals/{code}', path(code)))),
    impact: async (code) => {
      const impact = await unwrap(api.GET('/api/v1/deals/{code}/deletion-impact', path(code)))
      return { historyCount: impact.history_count, actionCount: impact.action_count, attachmentCount: impact.attachment_count }
    },
    create: async (input) => toDealDetail(await unwrap(api.POST('/api/v1/deals', { body: toCreateBody(input) }))),
    update: async (code, patch) =>
      toDealDetail(await unwrap(api.PATCH('/api/v1/deals/{code}', { ...path(code), body: toPatchBody(patch) }))),
    applyChange: async (code, request) => {
      const result = await unwrap(
        api.POST('/api/v1/deals/{code}/changes', { ...path(code), body: toChangeBody(request) }),
      )
      return { deal: toDealDetail(result.deal), coChanged: result.co_changed.map(toCoChange), notice: result.notice }
    },
    remove: (code, confirmCode) =>
      unwrapVoid(api.DELETE('/api/v1/deals/{code}', { params: { path: { code }, query: { confirm_code: confirmCode } } })),
  }
}
