import { api } from '../../shared/api/client'
import type { ActionQuery } from '../../shared/model/types'
import type { ActionsGateway } from '../types'
import { toNextActionStatusParam } from './mappers/nextActionStatus'
import { toActionCreateBody, toNextActionStatusBody, toActionUpdateBody, toDealAction } from './mappers/action'
import { unwrap, unwrapVoid } from './request'

const SORT = {
  actedAt: { asc: 'acted_at_asc', desc: 'acted_at_desc' },
  dueDate: { asc: 'due_date_asc', desc: 'due_date_desc' },
  actor: { asc: 'actor_asc', desc: 'actor_desc' },
  type: { asc: 'action_type_asc', desc: 'action_type_desc' },
  nextActionStatus: { asc: 'next_action_status_asc', desc: 'next_action_status_desc' },
} as const

/** 지정하지 않은 조건('' 포함)은 보내지 않는다. 서버에 페이지가 없으므로 offset/limit도 없다. */
function toListParams(q: ActionQuery) {
  return {
    ...(q.typeId ? { action_type_id: q.typeId } : {}),
    ...(q.actorId ? { actor_user_id: q.actorId } : {}),
    ...(q.keyword ? { keyword: q.keyword } : {}),
    ...(q.actedFrom ? { acted_from: q.actedFrom } : {}),
    ...(q.actedTo ? { acted_to: q.actedTo } : {}),
    ...(q.dueFrom ? { due_from: q.dueFrom } : {}),
    ...(q.dueTo ? { due_to: q.dueTo } : {}),
    ...(q.nextActionStatus ? { next_action_status: toNextActionStatusParam(q.nextActionStatus) } : {}),
    ...(q.sort && q.order ? { sort: SORT[q.sort][q.order] } : {}),
  }
}

export function createActionsHttp(): ActionsGateway {
  const byId = (actionId: number) => ({ params: { path: { action_id: actionId } } })
  return {
    list: async (dealCode, query) => {
      const result = await unwrap(
        api.GET('/api/v1/deals/{code}/actions', { params: { path: { code: dealCode }, query: toListParams(query) } }),
      )
      return result.items.map(toDealAction)
    },
    create: async (dealCode, input) =>
      toDealAction(
        await unwrap(
          api.POST('/api/v1/deals/{code}/actions', { params: { path: { code: dealCode } }, body: toActionCreateBody(input) }),
        ),
      ),
    update: async (actionId, input) =>
      toDealAction(await unwrap(api.PUT('/api/v1/deal-actions/{action_id}', { ...byId(actionId), body: toActionUpdateBody(input) }))),
    changeNextActionStatus: async (actionId, input) =>
      toDealAction(
        await unwrap(
          api.PUT('/api/v1/deal-actions/{action_id}/next-action-status', { ...byId(actionId), body: toNextActionStatusBody(input) }),
        ),
      ),
    remove: (actionId) => unwrapVoid(api.DELETE('/api/v1/deal-actions/{action_id}', byId(actionId))),
  }
}
