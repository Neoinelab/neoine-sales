import { useEffect, useRef, useState } from 'react'
import { formatDate } from '../../../shared/format'
import type { DealRow } from '../../../shared/model/types'
import { AmountText } from '../../../shared/ui/AmountText'
import { ForecastBadge, StatusBadge } from '../../../shared/ui/Badges'
import { InlineEditor } from './InlineEditor'
import { INLINE_LABEL, type InlineField } from './inline'

interface InlineCellProps {
  row: DealRow
  field: InlineField
  /** sales/admin만 true. false면 편집 버튼 없이 값만 보인다. */
  canWrite: boolean
  onSaved: (message: string) => void
}

function Display({ row, field }: { row: DealRow; field: InlineField }) {
  switch (field) {
    case 'statusKey':
      return <StatusBadge statusKey={row.statusKey} />
    case 'forecastKey':
      return <ForecastBadge forecastKey={row.forecastKey} />
    case 'revenueAmount':
      return <AmountText amount={row.revenueAmount} />
    case 'revenueDate':
      return <>{formatDate(row.revenueDate)}</>
  }
}

const SAVED_MARK_MS = 2500

/** Status/Forecast/금액/Expected Close 셀. 값을 누르면(또는 Enter) 편집 모드가 된다. */
export function InlineCell({ row, field, canWrite, onSaved }: InlineCellProps) {
  const [editing, setEditing] = useState(false)
  const [saved, setSaved] = useState(false)
  const button = useRef<HTMLButtonElement>(null)
  const wasEditing = useRef(false)

  // 편집을 마치면 편집 버튼으로 포커스를 돌려 키보드 흐름이 끊기지 않게 한다.
  useEffect(() => {
    if (wasEditing.current && !editing) button.current?.focus()
    wasEditing.current = editing
  }, [editing])

  useEffect(() => {
    if (!saved) return
    const timer = window.setTimeout(() => setSaved(false), SAVED_MARK_MS)
    return () => window.clearTimeout(timer)
  }, [saved])

  if (!canWrite) return <Display row={row} field={field} />
  if (editing) {
    return (
      <InlineEditor
        row={row}
        field={field}
        onDone={(message) => {
          setEditing(false)
          if (message) {
            setSaved(true)
            onSaved(message)
          }
        }}
      />
    )
  }
  return (
    <span className="cell-edit-wrap">
      <button
        ref={button}
        type="button"
        className="cell-edit"
        aria-label={`${row.name} ${INLINE_LABEL[field]} 편집`}
        onClick={() => setEditing(true)}
      >
        <Display row={row} field={field} />
      </button>
      {saved && (
        <span className="saved-mark" aria-hidden="true">
          ✓
        </span>
      )}
    </span>
  )
}
