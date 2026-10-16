import { api } from '../../shared/api/client'
import type { CodesGateway } from '../types'
import { toCodeSet, toCodeWithUsage } from './mappers/code'
import { unwrap, unwrapVoid } from './request'

export function createCodesHttp(): CodesGateway {
  return {
    all: async () => toCodeSet(await unwrap(api.GET('/api/v1/codes'))),
    list: async (kind) =>
      (await unwrap(api.GET('/api/v1/codes/usage', { params: { query: { kind } } }))).map(toCodeWithUsage),
    create: async (input) =>
      toCodeWithUsage(
        await unwrap(
          api.POST('/api/v1/codes', {
            body: { kind: input.kind, name: input.name, probability_hint: input.probabilityHint ?? null },
          }),
        ),
      ),
    rename: async (id, name) =>
      toCodeWithUsage(
        await unwrap(api.PATCH('/api/v1/codes/{code_id}', { params: { path: { code_id: id } }, body: { name } })),
      ),
    reorder: async (kind, orderedIds) =>
      (await unwrap(api.PUT('/api/v1/codes/order', { body: { kind, ordered_ids: orderedIds } }))).map(toCodeWithUsage),
    remove: (id) => unwrapVoid(api.DELETE('/api/v1/codes/{code_id}', { params: { path: { code_id: id } } })),
  }
}
