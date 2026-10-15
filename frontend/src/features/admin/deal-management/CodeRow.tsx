import { useId } from 'react'
import type { CodeWithUsage } from '../../../shared/model/types'
import { InlineNameEdit } from './InlineNameEdit'

export const LOCKED_HINT = '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.'

const OUTCOME_TEXT = { open: 'Open', won: 'Won', lost: 'Lost' } as const

interface Props {
  code: CodeWithUsage
  isFirst: boolean
  isLast: boolean
  editing: boolean
  busy: boolean
  onEdit: () => void
  onSaveName: (name: string) => void
  onCancelEdit: () => void
  onMove: (direction: -1 | 1) => void
  onDelete: () => void
}

/** Status/Forecast 코드 표의 한 행. 잠금(locked) 코드는 이름·순서는 바꿀 수 있고 삭제만 막는다. */
export function CodeRow({ code, isFirst, isLast, editing, busy, onEdit, onSaveName, onCancelEdit, onMove, onDelete }: Props) {
  const hintId = useId()
  const forecast = code.kind === 'forecast'
  return (
    <tr>
      <td className="num">{code.order}</td>
      <td>
        {editing ? (
          <InlineNameEdit label="코드 이름" initial={code.name} busy={busy} onSave={onSaveName} onCancel={onCancelEdit} />
        ) : (
          code.name
        )}
      </td>
      <td className="mono">{code.key}</td>
      {forecast && <td>{code.probabilityHint ?? '-'}</td>}
      {forecast && (
        <td>
          <span className="badge" data-outcome={code.outcome}>
            {OUTCOME_TEXT[code.outcome]}
          </span>
        </td>
      )}
      <td className="num stat">{code.usageCount}</td>
      <td>{code.locked ? <span className="badge">시스템 연결</span> : <span className="muted">-</span>}</td>
      <td>
        <div className="row-actions">
          <button type="button" className="small" aria-label={`${code.name} 위로 이동`} disabled={isFirst || busy} onClick={() => onMove(-1)}>
            ↑
          </button>
          <button type="button" className="small" aria-label={`${code.name} 아래로 이동`} disabled={isLast || busy} onClick={() => onMove(1)}>
            ↓
          </button>
          <button type="button" className="small" disabled={editing} onClick={onEdit}>
            이름 수정
          </button>
          <button
            type="button"
            className="small"
            disabled={code.locked || busy}
            aria-describedby={code.locked ? hintId : undefined}
            onClick={onDelete}
          >
            삭제
          </button>
          {code.locked && (
            <span id={hintId} className="sr-only">
              {LOCKED_HINT}
            </span>
          )}
        </div>
      </td>
    </tr>
  )
}
