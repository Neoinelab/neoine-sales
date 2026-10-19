import { api } from '../../shared/api/client'
import type { VendorsGateway } from '../types'
import { toSolution, toVendor } from './mappers/vendor'
import { unwrap, unwrapVoid } from './request'

export function createVendorsHttp(): VendorsGateway {
  const vendorPath = (vendorId: string) => ({ params: { path: { vendor_id: vendorId } } })
  const solutionPath = (vendorId: string, solutionId: string) => ({
    params: { path: { vendor_id: vendorId, solution_id: solutionId } },
  })
  return {
    list: async () => (await unwrap(api.GET('/api/v1/vendors'))).map(toVendor),
    create: async (name) => toVendor(await unwrap(api.POST('/api/v1/vendors', { body: { name } }))),
    rename: async (id, name) =>
      toVendor(await unwrap(api.PATCH('/api/v1/vendors/{vendor_id}', { ...vendorPath(id), body: { name } }))),
    remove: (id) => unwrapVoid(api.DELETE('/api/v1/vendors/{vendor_id}', vendorPath(id))),
    createSolution: async (vendorId, name) =>
      toSolution(
        await unwrap(api.POST('/api/v1/vendors/{vendor_id}/solutions', { ...vendorPath(vendorId), body: { name } })),
      ),
    renameSolution: async (vendorId, solutionId, name) =>
      toSolution(
        await unwrap(
          api.PATCH('/api/v1/vendors/{vendor_id}/solutions/{solution_id}', {
            ...solutionPath(vendorId, solutionId),
            body: { name },
          }),
        ),
      ),
    removeSolution: (vendorId, solutionId) =>
      unwrapVoid(api.DELETE('/api/v1/vendors/{vendor_id}/solutions/{solution_id}', solutionPath(vendorId, solutionId))),
  }
}
