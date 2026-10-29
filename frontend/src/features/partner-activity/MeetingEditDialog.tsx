import { useCallback, useRef, useState, type KeyboardEvent } from 'react'
import { useContactCompanies } from '../../data/contacts'
import { itemErrorsOf, useUpdateMeeting } from '../../data/partnerMeetings'
import type { PartnerMeeting } from '../../shared/model/types'
import { ErrorBanner } from '../../shared/ui/ErrorBanner'
import { Modal } from '../../shared/ui/Modal'
import { applyServerErrors, emptyRow, rowErrors, type EntryErrors, type EntryField, type EntryRow } from './entryRows'
import { MeetingEntryRow } from './MeetingEntryRow'
import './partner-activity.css'

const FIELD_ORDER: readonly EntryField[] = ['partnerCompany', 'dealCode', 'meetingDate', 'content']

interface MeetingEditDialogProps {
  meeting: PartnerMeeting
  onClose: () => void
}

function rowOf(meeting: PartnerMeeting): EntryRow {
  return {
    ...emptyRow(meeting.meetingDate),
    partnerText: meeting.partnerCompany,
    partnerCompany: meeting.partnerCompany,
    dealText: `${meeting.deal.name} [${meeting.deal.code}]`,
    dealCode: meeting.deal.code,
    meetingDate: meeting.meetingDate,
    content: meeting.content,
  }
}

/** 미팅 기록 한 건 수정. 입력 팝업과 같은 행을 하나 쓰고 행 추가는 없다. */
export function MeetingEditDialog({ meeting, onClose }: MeetingEditDialogProps) {
  const companies = useContactCompanies('partner').data ?? []
  const update = useUpdateMeeting()
  const [row, setRow] = useState<EntryRow>(() => rowOf(meeting))
  const [errors, setErrors] = useState<EntryErrors>({})
  const [focus, setFocus] = useState<EntryField | null>(null)
  const [formError, setFormError] = useState<unknown>(null)
  const saveRef = useRef<HTMLButtonElement>(null)
  const clearFocus = useCallback(() => setFocus(null), [])

  const onPatch = (patch: Partial<EntryRow>, edited?: EntryField) => {
    setRow((prev) => ({ ...prev, ...patch }))
    if (edited) setErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([key]) => key !== edited)))
  }

  function onContentKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey) return
    if (event.nativeEvent.isComposing || event.keyCode === 229) return
    event.preventDefault()
    saveRef.current?.focus()
  }

  async function save() {
    setFormError(null)
    const found = rowErrors(row)
    setErrors(found)
    const first = FIELD_ORDER.find((f) => found[f] !== undefined)
    if (first) {
      setFocus(first)
      return
    }
    try {
      await update.mutateAsync({ id: meeting.id, input: { partnerCompany: row.partnerCompany, dealCode: row.dealCode, meetingDate: row.meetingDate, content: row.content } })
      onClose()
    } catch (caught) {
      const located = applyServerErrors(itemErrorsOf(caught).map((e) => ({ ...e, location: ['items', 0, ...e.location] })), [0])[0]
      const placed = located ? FIELD_ORDER.find((f) => located[f] !== undefined) : undefined
      if (located && placed) {
        setErrors(located)
        setFocus(placed)
      } else {
        setFormError(caught)
      }
    }
  }

  return (
    <Modal
      title="미팅 수정"
      wide
      onClose={onClose}
      footer={
        <>
          <button type="button" onClick={onClose}>
            취소
          </button>
          <button type="button" ref={saveRef} className="primary" disabled={update.isPending} onClick={() => void save()}>
            저장
          </button>
        </>
      }
    >
      <div className="meeting-entry-rows">
        <MeetingEntryRow
          number={1}
          row={row}
          errors={errors}
          companies={companies}
          focusField={focus}
          onFocused={clearFocus}
          onPatch={onPatch}
          onContentKeyDown={onContentKeyDown}
          autoFocusContent
        />
      </div>
      <ErrorBanner error={formError} />
    </Modal>
  )
}
