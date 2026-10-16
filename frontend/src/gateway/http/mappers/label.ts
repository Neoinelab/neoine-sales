import type { Schemas } from '../../../shared/api/client'
import type { BantLabelWithUsage } from '../../../shared/model/types'
import { toUserRef } from './user'

export function toLabel(row: Schemas['BantLabelResponse']): BantLabelWithUsage {
  return {
    id: row.id,
    category: row.category,
    name: row.name,
    isDefault: row.is_default,
    createdBy: row.created_by === null ? null : toUserRef(row.created_by),
    createdAt: row.created_at,
    usageCount: row.usage_count,
  }
}
