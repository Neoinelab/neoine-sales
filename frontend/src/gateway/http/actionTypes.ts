import { api } from '../../shared/api/client'
import type { ActionTypesGateway } from '../types'
import { toActionType } from './mappers/actionType'
import { unwrap, unwrapVoid } from './request'

export function createActionTypesHttp(): ActionTypesGateway {
  const byId = (id: string) => ({ params: { path: { type_id: id } } })
  return {
    list: async () => (await unwrap(api.GET('/api/v1/action-types'))).map(toActionType),
    create: async (name) => toActionType(await unwrap(api.POST('/api/v1/action-types', { body: { name } }))),
    rename: async (id, name) =>
      toActionType(await unwrap(api.PATCH('/api/v1/action-types/{type_id}', { ...byId(id), body: { name } }))),
    remove: (id) => unwrapVoid(api.DELETE('/api/v1/action-types/{type_id}', byId(id))),
  }
}
