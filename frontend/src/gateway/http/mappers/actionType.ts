import type { Schemas } from '../../../shared/api/client'
import type { ActionTypeWithUsage } from '../../../shared/model/types'
import { toUserRef } from './user'

export function toActionType(row: Schemas['ActionTypeResponse']): ActionTypeWithUsage {
  return {
    id: row.id,
    name: row.name,
    isDefault: row.is_default,
    createdBy: row.created_by === null ? null : toUserRef(row.created_by),
    usageCount: row.usage_count,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}
