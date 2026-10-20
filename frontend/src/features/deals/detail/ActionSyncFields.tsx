import { useId, type ReactNode } from 'react'
import { useCodeSet } from '../../../data/codes'
import type { SyncChange } from '../../../shared/model/sync'
import type { Code } from '../../../shared/model/types'
import { SyncNotice } from '../../../shared/sync/SyncNotice'
import type { ActionSync } from './useActionSync'

interface ActionSyncFieldsProps {
  sync: ActionSync
  /** 같은 줄의 세 번째 칸(유형 입력). */
  children: ReactNode
}

interface SelectCellProps {
  label: string
  field: SyncChange['field']
  list: readonly Code[]
  sync: ActionSync
}

function SelectCell({ label, field, list, sync }: SelectCellProps) {
  const hintId = useId()
  const changed = sync.state[field] !== sync.base[field]
  const originalName = list.find((c) => c.key === sync.base[field])?.name ?? sync.base[field]
  return (
    <div className="dd-sync-cell">
      <label className="field">
        <span>{label}</span>
        <select
          aria-describedby={changed ? hintId : undefined}
          value={sync.state[field]} onChange={(e) => void sync.change(field, e.target.value)}>
          {list.map((c) => (
            <option key={c.key} value={c.key}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      {changed && <p id={hintId} className="field-hint">현재: {originalName}</p>}
    </div>
  )
}

/** Action 등록 폼 상단 한 줄: Status · Forecast · 유형(좁은 화면에서는 한 열). 변경 안내·충돌·취소 버튼을 함께 그린다. */
export function ActionSyncFields({ sync, children }: ActionSyncFieldsProps) {
  const codes = useCodeSet().data
  return (
    <>
      <div role="group" aria-label="Status · Forecast · 유형" className="dd-sync-row">
        {codes && <SelectCell label="Status" field="statusKey" list={codes.statuses} sync={sync} />}
        {codes && <SelectCell label="Forecast" field="forecastKey" list={codes.forecasts} sync={sync} />}
        <div className="dd-sync-cell">{children}</div>
      </div>
      {sync.conflict && (
        <p role="alert" className="field-error">
          {sync.conflict}
        </p>
      )}
      <p role="status" className="field-hint">
        {sync.reverted}
      </p>
      <SyncNotice notice={sync.entries.map((e) => e.applied.notice)} draft />
      {sync.entries.length > 0 && (
        <div>
          <button type="button" className="dd-small" onClick={sync.reset}>
            Status·Forecast 변경 취소
          </button>
        </div>
      )}
    </>
  )
}
