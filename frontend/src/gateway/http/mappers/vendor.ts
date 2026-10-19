import type { Schemas } from '../../../shared/api/client'
import type { Solution, Vendor } from '../../../shared/model/types'

export function toSolution(row: Schemas['SolutionResponse']): Solution {
  return { id: row.id, vendorId: row.vendor_id, name: row.name, usageCount: row.usage_count }
}

export function toVendor(row: Schemas['VendorResponse']): Vendor {
  return { id: row.id, name: row.name, usageCount: row.usage_count, solutions: row.solutions.map(toSolution) }
}
