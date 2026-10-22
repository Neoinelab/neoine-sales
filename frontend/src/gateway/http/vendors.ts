import { api } from '../../shared/api/client'
import type { VendorsGateway } from '../types'
import { toVendor } from './mappers/vendor'
import { unwrap, unwrapVoid } from './request'

export function createVendorsHttp(): VendorsGateway {
  const vendorPath = (vendorId: number) => ({ params: { path: { vendor_id: vendorId } } })
  return {
    list: async () => (await unwrap(api.GET('/api/v1/vendors'))).map(toVendor),
    create: async (name) => toVendor(await unwrap(api.POST('/api/v1/vendors', { body: { name } }))),
    rename: async (id, name) =>
      toVendor(await unwrap(api.PATCH('/api/v1/vendors/{vendor_id}', { ...vendorPath(id), body: { name } }))),
    remove: (id) => unwrapVoid(api.DELETE('/api/v1/vendors/{vendor_id}', vendorPath(id))),
  }
}
