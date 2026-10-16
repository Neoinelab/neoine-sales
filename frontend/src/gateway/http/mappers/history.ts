import type { Schemas } from '../../../shared/api/client'
import type { HistoryEntry } from '../../../shared/model/types'
import { toUserRef } from './user'

export function toHistoryEntry(row: Schemas['HistoryEntryResponse']): HistoryEntry {
  return {
    id: row.id,
    dealCode: row.deal_code,
    at: row.at,
    by: toUserRef(row.by),
    category: row.category,
    target: row.target,
    before: row.before,
    after: row.after,
  }
}
