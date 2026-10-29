import { useCallback, useState, type KeyboardEvent } from 'react'
import { useContactCompanies } from '../../data/contacts'
import { itemErrorsOf, useCreateMeetings } from '../../data/partnerMeetings'
import { useToday } from '../../data/today'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Modal } from '../../shared/ui/Modal'
import {
  MAX_ROWS,
  applyServerErrors,
  emptyRow,
  firstMissingField,
  isBlank,
  rowsToInputs,
  validateRows,
  type EntryField,
  type EntryRow,
  type RowErrors,
} from './entryRows'
import { MeetingEntryRow } from './MeetingEntryRow'
import './partner-activity.css'

const FIELD_ORDER: readonly EntryField[] = ['partnerCompany', 'dealCode', 'meetingDate', 'content']
const LIMIT_MESSAGE = `한 번에 ${MAX_ROWS}건까지 입력할 수 있습니다.`
const NOTHING_MESSAGE = '입력한 미팅이 없습니다.'

interface MeetingEntryDialogProps {
  onClose: () => void
  /** 저장 성공(알림 문구와 함께). 팝업을 닫는 일은 호출처가 한다. */
  onSaved: (message: string) => void
}

/** 첫 오류가 있는 행·칸(행 순서, 칸 순서). */
function firstError(errors: RowErrors): { index: number; field: EntryField } | null {
  const index = Object.keys(errors).map(Number).sort((a, b) => a - b)[0]
  if (index === undefined) return null
  const field = FIELD_ORDER.find((f) => errors[index]?.[f] !== undefined)
  return field ? { index, field } : null
}

/** 여러 건의 파트너 미팅을 한 번에 입력하는 팝업. 빈 행은 건너뛰고, 서버는 전체를 원자적으로 저장한다. */
export function MeetingEntryDialog({ onClose, onSaved }: MeetingEntryDialogProps) {
  const { today } = useToday()
  const companies = useContactCompanies('partner').data ?? []
  const create = useCreateMeetings()
  const [rows, setRows] = useState<EntryRow[]>(() => [emptyRow(today)])
  const [errors, setErrors] = useState<RowErrors>({})
  const [focus, setFocus] = useState<{ index: number; field: EntryField } | null>(null)
  const [formError, setFormError] = useState<unknown>(null)
  const [nothing, setNothing] = useState(false)
  const [limit, setLimit] = useState(false)
  const [asking, setAsking] = useState(false)
  const clearFocus = useCallback(() => setFocus(null), [])

  const patchRow = (index: number, patch: Partial<EntryRow>, edited?: EntryField) => {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)))
    if (edited) {
      setErrors((prev) => {
        if (prev[index]?.[edited] === undefined) return prev
        return { ...prev, [index]: Object.fromEntries(Object.entries(prev[index]).filter(([key]) => key !== edited)) }
      })
    }
  }

  function addRow(): number {
    if (rows.length >= MAX_ROWS) {
      setLimit(true)
      return -1
    }
    setRows((prev) => [...prev, emptyRow(today)])
    setLimit(false)
    return rows.length
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index))
    // 지운 행 뒤의 오류는 한 칸씩 당긴다.
    setErrors((prev) =>
      Object.fromEntries(Object.entries(prev).filter(([key]) => Number(key) !== index).map(([key, value]) => [Number(key) > index ? Number(key) - 1 : Number(key), value])),
    )
    setLimit(false)
  }

  function onContentKeyDown(index: number, event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) return
    // 한글 조합을 확정하는 Enter는 그대로 둔다.
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    const row = rows[index]
    if (!row) return
    const missing = firstMissingField(row)
    if (missing) {
      setFocus({ index, field: missing })
      return
    }
    if (index < rows.length - 1) {
      setFocus({ index: index + 1, field: 'partnerCompany' })
      return
    }
    const added = addRow()
    if (added >= 0) setFocus({ index: added, field: 'partnerCompany' })
  }

  async function save() {
    setFormError(null)
    setNothing(false)
    setLimit(false)
    const { inputs, rowIndexOf } = rowsToInputs(rows)
    if (inputs.length === 0) {
      setNothing(true)
      return
    }
    const found = validateRows(rows)
    setErrors(found)
    const first = firstError(found)
    if (first) {
      setFocus(first)
      return
    }
    try {
      await create.mutateAsync(inputs)
      onSaved(`미팅 ${inputs.length}건을 저장했습니다.`)
    } catch (caught) {
      // 아무것도 저장되지 않았다: 입력은 유지하고 거절된 행·칸 아래에 서버 문구를 보인다.
      const located = applyServerErrors(itemErrorsOf(caught), rowIndexOf)
      const placed = firstError(located)
      if (placed) {
        setErrors(located)
        setFocus(placed)
      } else {
        setFormError(caught)
      }
    }
  }

  function requestClose() {
    if (rows.some((row) => !isBlank(row))) setAsking(true)
    else onClose()
  }

  return (
    <>
      <Modal
        title="미팅 내용 입력"
        wide
        onClose={requestClose}
        footer={
          <>
            <button type="button" onClick={requestClose}>
              취소
            </button>
            <button type="button" className="primary" disabled={create.isPending} onClick={() => void save()}>
              저장
            </button>
          </>
        }
      >
        <div className="meeting-entry-rows">
          {rows.map((row, index) => (
            <MeetingEntryRow
              key={row.key}
              number={index + 1}
              row={row}
              errors={errors[index] ?? {}}
              companies={companies}
              focusField={focus?.index === index ? focus.field : null}
              onFocused={clearFocus}
              onPatch={(patch, edited) => patchRow(index, patch, edited)}
              onRemove={() => removeRow(index)}
              removeDisabled={rows.length === 1}
              onContentKeyDown={(event) => onContentKeyDown(index, event)}
            />
          ))}
        </div>
        <div>
          <button type="button" onClick={() => addRow()}>
            행 추가
          </button>
        </div>
        {limit && (
          <p role="alert" className="error">
            {LIMIT_MESSAGE}
          </p>
        )}
        {nothing && (
          <p role="alert" className="error">
            {NOTHING_MESSAGE}
          </p>
        )}
        <ErrorBanner error={formError} />
      </Modal>
      {asking && (
        <ConfirmDialog title="입력 취소" message="입력한 내용을 버릴까요?" confirmLabel="버리기" cancelLabel="계속 입력" danger onConfirm={onClose} onCancel={() => setAsking(false)} />
      )}
    </>
  )
}
