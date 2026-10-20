/** Action 등록 폼의 Status·Forecast 변경 목록(draft) 순수 도우미. 변경은 사용자가 바꾼 순서대로 쌓인다. */
import type { StatusChangeRequest } from '../../../shared/model/inputs'
import type { SyncApplied, SyncChange, SyncState } from '../../../shared/model/sync'
import { withRo } from '../../../shared/model/text'
import type { CodeSet } from '../../../shared/model/types'
import { toResolution } from './detailHelpers'

export interface SyncEntry {
  change: SyncChange
  applied: SyncApplied
}

type Field = SyncChange['field']

/** base에 각 변경의 patch를 순서대로 적용한 상태. */
export function stateOf(base: SyncState, entries: readonly SyncEntry[]): SyncState {
  return entries.reduce<SyncState>(
    (state, e) => ({
      statusKey: e.applied.patch.statusKey ?? state.statusKey,
      forecastKey: e.applied.patch.forecastKey ?? state.forecastKey,
    }),
    base,
  )
}

/** field의 변경과 그 이후 변경을 버린다. alsoDropped는 함께 버려진 다른 필드(안내용). 변경이 없는 필드면 그대로. */
export function dropFrom(entries: readonly SyncEntry[], field: Field): { kept: SyncEntry[]; alsoDropped: Field[] } {
  const index = entries.findIndex((e) => e.change.field === field)
  if (index < 0) return { kept: [...entries], alsoDropped: [] }
  return { kept: entries.slice(0, index), alsoDropped: entries.slice(index + 1).map((e) => e.change.field) }
}

/** 요청 본문용: 변경 순서를 지키고 각 변경에 자기 resolution만 붙인다. */
export function toStatusChanges(entries: readonly SyncEntry[]): StatusChangeRequest[] {
  return entries.map((e) => ({ change: e.change, resolution: toResolution(e.applied) }))
}

function nameOf(list: CodeSet['statuses'], key: string): string {
  return list.find((c) => c.key === key)?.name ?? key
}

/** "'이름'으로" 형태(받침에 맞는 조사). */
function quotedRo(name: string): string {
  return `'${name}'${withRo(name).slice(name.length)}`
}

/** 최종 상태가 base와 다른 필드만 말한다(Status 먼저). 다른 것이 없으면 null. */
export function changeSummary(base: SyncState, entries: readonly SyncEntry[], codes: CodeSet): string | null {
  const last = stateOf(base, entries)
  const parts: string[] = []
  if (last.statusKey !== base.statusKey) parts.push(`Status가 ${quotedRo(nameOf(codes.statuses, last.statusKey))}`)
  if (last.forecastKey !== base.forecastKey) parts.push(`Forecast가 ${quotedRo(nameOf(codes.forecasts, last.forecastKey))}`)
  return parts.length === 0 ? null : `${parts.join(', ')} 변경되었습니다.`
}
