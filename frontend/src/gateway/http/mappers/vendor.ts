import type { Schemas } from '../../../shared/api/client'
import type { Vendor } from '../../../shared/model/types'

export function toVendor(row: Schemas['VendorResponse']): Vendor {
  return { id: row.id, name: row.name, usageCount: row.usage_count }
}
