import { api } from '../../shared/api/client'
import type { LabelsGateway } from '../types'
import { toLabel } from './mappers/label'
import { unwrap, unwrapVoid } from './request'

export function createLabelsHttp(): LabelsGateway {
  return {
    list: async () => (await unwrap(api.GET('/api/v1/bant-labels'))).map(toLabel),
    create: async (category, name) =>
      toLabel(await unwrap(api.POST('/api/v1/bant-labels', { body: { category, name } }))),
    rename: async (id, name) =>
      toLabel(
        await unwrap(
          api.PATCH('/api/v1/bant-labels/{label_id}', { params: { path: { label_id: id } }, body: { name } }),
        ),
      ),
    remove: (id) => unwrapVoid(api.DELETE('/api/v1/bant-labels/{label_id}', { params: { path: { label_id: id } } })),
  }
}
