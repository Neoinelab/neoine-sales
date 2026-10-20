import { useState } from 'react'
import { certainlyOverrides, overridesRequested, SYNC_CONFLICT_MESSAGE, type SyncChange, type SyncState } from '../../../shared/model/sync'
import type { DealDetail } from '../../../shared/model/types'
import { useSyncedChange } from '../../../shared/sync/useSyncedChange'
import { dropFrom, stateOf, type SyncEntry } from './syncDraft'

type Field = SyncChange['field']

const FIELD_LABEL: Record<Field, string> = { statusKey: 'Status', forecastKey: 'Forecast' }

/**
 * Action 등록 폼의 Status·Forecast 변경 목록. 변경은 바꾼 순서대로 쌓이고 각각 직전 상태 기준으로 판정한다.
 * 먼저 바꾼 값을 되돌리는 변경(서버가 422로 거절할 것)은 저장 전에 막는다.
 */
export function useActionSync(deal: DealDetail) {
  const { request, dialogs } = useSyncedChange(deal)
  const [entries, setEntries] = useState<SyncEntry[]>([])
  const [conflict, setConflict] = useState<string | null>(null)
  const [reverted, setReverted] = useState<string | null>(null)
  const [error, setError] = useState<unknown>(null)
  const base: SyncState = { statusKey: deal.statusKey, forecastKey: deal.forecastKey }
  const state = stateOf(base, entries)

  function settle(next: SyncEntry[], alsoDropped: Field[]) {
    setEntries(next)
    setConflict(null)
    setError(null)
    const other = alsoDropped[0]
    setReverted(other ? `${FIELD_LABEL[other]} 변경도 취소되었습니다. 필요하면 다시 선택하세요.` : null)
  }

  async function change(field: Field, value: string) {
    // 이 필드의 이전 변경과 그 뒤 변경은 버리고, 남는 변경(최대 1개) 뒤의 상태에서 새 값을 판정한다.
    const { kept, alsoDropped } = dropFrom(entries, field)
    const before = stateOf(base, kept)
    if (value === before[field]) {
      if (kept.length < entries.length) settle(kept, alsoDropped)
      return
    }
    const first = kept[0]?.change
    const options = first
      ? {
          from: { ...deal, ...before },
          guard: (plan: Parameters<typeof certainlyOverrides>[2], at: SyncState) => (certainlyOverrides(first, at, plan) ? SYNC_CONFLICT_MESSAGE : null),
        }
      : undefined
    const requested: SyncChange = { field, value }
    try {
      const applied = await request(requested, options)
      if (applied === null) return
      if (first && overridesRequested(first, before, applied)) throw new Error(SYNC_CONFLICT_MESSAGE)
      settle([...kept, { change: requested, applied }], alsoDropped)
    } catch (caught) {
      if (caught instanceof Error && caught.message === SYNC_CONFLICT_MESSAGE) {
        setReverted(null)
        setConflict(SYNC_CONFLICT_MESSAGE)
      } else {
        setError(caught)
      }
    }
  }

  function reset() {
    settle([], [])
  }

  return { base, state, entries, conflict, reverted, error, dialogs, change, reset }
}

export type ActionSync = ReturnType<typeof useActionSync>
