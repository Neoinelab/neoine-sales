import { useCallback, useState } from 'react'
import { useContactCompanies } from '../../data/contacts'
import { itemErrorsOf, useCreateMeetings } from '../../data/partnerMeetings'
import { useToday } from '../../data/today'
import { ConfirmDialog } from '../../shared/ui/ConfirmDialog'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Modal } from '../../shared/ui/Modal'
import {
  applyServerErrors,
  emptyRow,
  isBlank,
  rowsToInputs,
  validateRows,
  type EntryField,
  type EntryRow,
  type RowErrors,
} from './entryRows'
import { MeetingEntryRow } from './MeetingEntryRow'
import './partner-activity.css'

const FIELD_ORDER: readonly EntryField[] = ['partnerCompany', 'meetingDate', 'content']
const NOTHING_MESSAGE = '입력한 미팅이 없습니다.'

interface MeetingEntryDialogProps {
  onClose: () => void
  /** 저장 성공(알림 문구와 함께). 팝업을 닫는 일은 호출처가 한다. */
  onSaved: (message: string) => void
}

/** 입력 한 건의 첫 오류 칸(파트너, 날짜, 내용 순서). */
function firstError(errors: RowErrors): EntryField | null {
  return FIELD_ORDER.find((field) => errors[0]?.[field] !== undefined) ?? null
}

/** 파트너 미팅 한 건을 입력하고 기존 일괄 등록 API에 항목 하나로 저장한다. */
export function MeetingEntryDialog({ onClose, onSaved }: MeetingEntryDialogProps) {
  const { today } = useToday()
  const companies = useContactCompanies('partner').data ?? []
  const create = useCreateMeetings()
  const [row, setRow] = useState<EntryRow>(() => emptyRow(today))
  const [errors, setErrors] = useState<RowErrors>({})
  const [focus, setFocus] = useState<EntryField | null>(null)
  const [formError, setFormError] = useState<unknown>(null)
  const [nothing, setNothing] = useState(false)
  const [asking, setAsking] = useState(false)
  const clearFocus = useCallback(() => setFocus(null), [])

  const patchRow = (patch: Partial<EntryRow>, edited?: EntryField) => {
    setRow((prev) => ({ ...prev, ...patch }))
    if (edited) {
      setErrors((prev) => {
        if (prev[0]?.[edited] === undefined) return prev
        return { ...prev, [0]: Object.fromEntries(Object.entries(prev[0]).filter(([key]) => key !== edited)) }
      })
    }
  }

  async function save() {
    setFormError(null)
    setNothing(false)
    const { inputs, rowIndexOf } = rowsToInputs([row])
    if (inputs.length === 0) {
      setNothing(true)
      return
    }
    const found = validateRows([row])
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
    if (!isBlank(row)) setAsking(true)
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
          <MeetingEntryRow
            number={1}
            row={row}
            errors={errors[0] ?? {}}
            companies={companies}
            focusField={focus}
            onFocused={clearFocus}
            onPatch={patchRow}
          />
        </div>
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
