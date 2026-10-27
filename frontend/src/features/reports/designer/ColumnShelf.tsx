import { useEffect, useRef, useState, type DragEvent, type KeyboardEvent } from 'react'
import type { ReportCatalog } from '../../../shared/model/reportTypes'
import { ColumnSettings } from './ColumnSettings'
import { columnName } from './names'
import { fieldByKey } from './state/columnRules'
import type { DesignerAction, DesignerColumn, DesignerState } from './state/designerState'
import { idsOf, type IssueView, type Message } from './state/issueView'

/** 설정 패널이 자기 입력에 붙이는 위반의 part. 이 밖의 위반은 칩 쪽에 보인다. */
const PANEL_PARTS = ['label', 'format', 'prefix_length', 'group', 'aggregate']

interface ColumnShelfProps {
  state: DesignerState
  catalog: ReportCatalog
  issues: IssueView
  dispatch: (action: DesignerAction) => void
}

function badgesOf(column: DesignerColumn, catalog: ReportCatalog, hasGroup: boolean): string[] {
  const field = fieldByKey(catalog, column.field)
  if (!field) return []
  const badges: string[] = []
  if (column.group) badges.push('그룹')
  else if (column.aggregate) badges.push(catalog.aggregates.find((a) => a.key === column.aggregate)?.label ?? column.aggregate)
  if (column.format !== field.defaultFormat) badges.push(catalog.formats.find((f) => f.key === column.format)?.label ?? column.format)
  if (field.requiresGrouping && !hasGroup) badges.push('그룹핑할 때만')
  return badges
}

/** 컬럼 칩 목록(끌어서 놓기·Alt+←/→로 순서 변경)과 선택한 칩의 설정 패널. */
export function ColumnShelf({ state, catalog, issues, dispatch }: ColumnShelfProps) {
  const { columns, selectedUid } = state
  const [announcement, setAnnouncement] = useState('')
  const dragUid = useRef<number | null>(null)
  const [overUid, setOverUid] = useState<number | null>(null)
  const chipRefs = useRef(new Map<number, HTMLButtonElement>())
  const focusAfterMove = useRef<number | null>(null)
  const hasGroup = columns.some((c) => c.group)
  const full = columns.length >= catalog.limits.columnsMax

  // 칩을 옮긴 뒤 DOM이 다시 배치되면 키보드로 옮긴 칩에 포커스를 되돌린다.
  useEffect(() => {
    const uid = focusAfterMove.current
    if (uid === null) return
    focusAfterMove.current = null
    chipRefs.current.get(uid)?.focus()
  })

  const move = (column: DesignerColumn, to: number) => {
    if (to < 0 || to >= columns.length || to === columns.indexOf(column)) return
    dispatch({ type: 'moveColumn', uid: column.uid, to })
    setAnnouncement(`‘${columnName(column, catalog)}’를 ${to + 1}번째로 옮겼습니다`)
  }

  const onKeyDown = (event: KeyboardEvent, column: DesignerColumn, index: number) => {
    if (!event.altKey || (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight')) return
    event.preventDefault()
    const to = event.key === 'ArrowLeft' ? index - 1 : index + 1
    if (to < 0 || to >= columns.length) return
    focusAfterMove.current = column.uid
    move(column, to)
  }

  const endDrag = () => {
    dragUid.current = null
    setOverUid(null)
  }

  const onDrop = (event: DragEvent, targetIndex: number) => {
    event.preventDefault()
    const uid = dragUid.current
    const dragged = columns.find((c) => c.uid === uid)
    endDrag()
    if (dragged) move(dragged, targetIndex)
  }

  const selected = columns.find((c) => c.uid === selectedUid)
  const selectedField = selected ? fieldByKey(catalog, selected.field) : undefined
  const selectedIndex = selected ? columns.indexOf(selected) : -1

  const chipMessages = (column: DesignerColumn): readonly Message[] => {
    const all = issues.column(column.uid)
    return column.uid === selectedUid ? all.filter((m) => m.part === null || !PANEL_PARTS.includes(m.part)) : all
  }

  return (
    <section className="report-card" aria-labelledby="report-columns-title">
      <h2 id="report-columns-title">컬럼</h2>
      {columns.length === 0 ? (
        <p className="hint">왼쪽 필드 목록에서 컬럼을 추가하세요.</p>
      ) : (
        <ul className="report-chips" aria-label="컬럼">
          {columns.map((column, index) => {
            const name = columnName(column, catalog)
            const own = chipMessages(column)
            const invalid = issues.column(column.uid).length > 0
            const isSelected = column.uid === selectedUid
            return (
              <li
                key={column.uid}
                className={`report-chip${isSelected ? ' is-selected' : ''}${invalid ? ' is-invalid' : ''}${overUid === column.uid ? ' is-over' : ''}${fieldByKey(catalog, column.field)?.entity === 'action' ? ' is-action' : ''}`}
                draggable
                onDragStart={(event) => {
                  dragUid.current = column.uid
                  event.dataTransfer.effectAllowed = 'move'
                  event.dataTransfer.setData('text/plain', String(column.uid))
                }}
                onDragOver={(event) => {
                  if (dragUid.current === null) return
                  event.preventDefault()
                  if (overUid !== column.uid) setOverUid(column.uid)
                }}
                onDrop={(event) => onDrop(event, index)}
                onDragEnd={endDrag}
              >
                <button
                  type="button"
                  className="report-chip-main"
                  ref={(node) => {
                    if (node) chipRefs.current.set(column.uid, node)
                    else chipRefs.current.delete(column.uid)
                  }}
                  aria-pressed={isSelected}
                  aria-describedby={idsOf(own)}
                  onClick={() => dispatch({ type: 'selectColumn', uid: column.uid })}
                  onKeyDown={(event) => onKeyDown(event, column, index)}
                >
                  <span className="report-chip-name">{name}</span>
                  {badgesOf(column, catalog, hasGroup).map((badge) => (
                    <span key={badge} className="report-badge">
                      {badge}
                    </span>
                  ))}
                </button>
                <button type="button" className="report-chip-remove" aria-label={`${name} 빼기`} onClick={() => dispatch({ type: 'removeColumn', uid: column.uid })}>
                  ×
                </button>
                {own.map((m) => (
                  <p key={m.id} id={m.id} className="field-error report-chip-error">
                    {m.text}
                  </p>
                ))}
              </li>
            )
          })}
        </ul>
      )}
      {full && <p className="hint">컬럼은 최대 {catalog.limits.columnsMax}개입니다</p>}
      {issues.columns.map((m) => (
        <p key={m.id} id={m.id} className="field-error">
          {m.text}
        </p>
      ))}
      <p className="report-sr" aria-live="polite">
        {announcement}
      </p>
      {selected && selectedField && (
        <ColumnSettings
          column={selected}
          field={selectedField}
          catalog={catalog}
          hasGroup={hasGroup}
          index={selectedIndex}
          count={columns.length}
          messages={issues.column(selected.uid).filter((m) => m.part !== null && PANEL_PARTS.includes(m.part))}
          onPatch={(patch) => dispatch({ type: 'updateColumn', uid: selected.uid, patch })}
          onMove={(to) => move(selected, to)}
        />
      )}
    </section>
  )
}
