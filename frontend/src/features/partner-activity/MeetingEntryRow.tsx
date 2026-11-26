import { useEffect, useId, useRef, useState, type KeyboardEvent, type Ref } from 'react'
import { isDateValue } from '../../shared/model/dateText'
import { ComboBox } from '../../shared/ui/ComboBox'
import { DateInput } from '../../shared/ui/DateInput'
import type { EntryErrors, EntryField, EntryRow } from './entryRows'

interface MeetingEntryRowProps {
  /** 화면에 보이는 번호(1부터). */
  number: number
  row: EntryRow
  errors: EntryErrors
  companies: readonly string[]
  /** 이 행의 칸 하나로 포커스를 옮겨 달라는 요청(옮기면 onFocused를 부른다). */
  focusField: EntryField | null
  onFocused: () => void
  onPatch: (patch: Partial<EntryRow>, edited?: EntryField) => void
  /** 열릴 때 내용 칸에 포커스를 둔다(수정 팝업). */
  autoFocusContent?: boolean
}

const NOT_LISTED = '목록에서 선택하세요.'

/** 입력 팝업의 한 행: 파트너 -> 미팅 날짜 -> 미팅 내용. 칸 이동은 선택·Enter로 이어진다. */
export function MeetingEntryRow(props: MeetingEntryRowProps) {
  const { number, row, errors, companies, focusField, onFocused, onPatch, autoFocusContent } = props
  const partnerRef = useRef<HTMLInputElement>(null)
  const dateRef = useRef<HTMLInputElement>(null)
  const contentRef = useRef<HTMLTextAreaElement>(null)
  const dateId = useId()
  const contentId = useId()
  const contentErrorId = `${contentId}-error`
  // 파트너를 고른 뒤 날짜 칸으로 포커스를 옮긴다(선택 핸들러가 행 상태도 바꾸므로 반드시 다시 그려진다).
  const ownFocus = useRef<EntryField | null>(null)
  // 글자를 쳐 Enter를 눌렀지만 목록에 같은 항목이 없을 때의 안내.
  const [notListed, setNotListed] = useState(false)

  useEffect(() => {
    const wanted = focusField ?? ownFocus.current
    if (!wanted) return
    ownFocus.current = null
    const target = { partnerCompany: partnerRef, meetingDate: dateRef, content: contentRef }[wanted]
    target.current?.focus()
    if (focusField) onFocused()
  })

  /** 닫힌 목록(또는 활성 항목 없는 목록)에서 Enter는 다음 칸으로. 목록의 활성 항목 선택은 ComboBox가 먼저 처리한다. */
  function moveOnWithEnter(event: KeyboardEvent<HTMLDivElement>, next: () => void) {
    if (event.key !== 'Enter' || event.isDefaultPrevented() || event.nativeEvent.isComposing) return
    event.preventDefault()
    next()
  }

  function choosePartner(company: string) {
    onPatch({ partnerText: company, partnerCompany: company }, 'partnerCompany')
    ownFocus.current = 'meetingDate'
    setNotListed(false)
  }

  /** 목록 글자와 정확히 같은 글자(대소문자·앞뒤 공백 무시)는 목록에서 고른 것으로 본다. */
  function sameText(a: string, b: string): boolean {
    return a.trim().toLowerCase() === b.trim().toLowerCase()
  }

  function enterOnPartner() {
    if (row.partnerText.trim() === '') {
      if (row.partnerCompany !== '') dateRef.current?.focus()
      return
    }
    const match = companies.find((c) => sameText(c, row.partnerText))
    if (match) choosePartner(match)
    else setNotListed(true)
  }

  return (
    <div role="group" aria-label={`미팅 ${number}`} className="meeting-entry-row">
      <div role="presentation" className="meeting-entry-cell" onKeyDown={(e) => moveOnWithEnter(e, enterOnPartner)}>
        <ComboBox
          label="파트너"
          openOnFocus={false}
          name={`partner-${row.key}`}
          value={row.partnerText}
          options={companies.map((c) => ({ value: c }))}
          inputRef={partnerRef as Ref<HTMLInputElement>}
          error={errors.partnerCompany ?? (notListed ? NOT_LISTED : undefined)}
          onChange={(text) => {
            setNotListed(false)
            onPatch({ partnerText: text, partnerCompany: '' }, 'partnerCompany')
          }}
          onSelectOption={(option) => choosePartner(option.value)}
        />
      </div>
      <div className="field meeting-entry-cell">
        <label htmlFor={dateId}>미팅 날짜</label>
        <DateInput
          id={dateId}
          aria-label="미팅 날짜"
          value={row.meetingDate}
          error={errors.meetingDate}
          inputRef={dateRef}
          onChange={(meetingDate) => onPatch({ meetingDate }, 'meetingDate')}
          onEnter={(value) => {
            if (isDateValue(value)) contentRef.current?.focus()
          }}
          onPicked={() => contentRef.current?.focus()}
        />
      </div>
      <div className="field meeting-entry-content">
        <label htmlFor={contentId}>미팅 내용</label>
        <textarea
          id={contentId}
          ref={contentRef}
          rows={6}
          value={row.content}
          data-autofocus={autoFocusContent ? '' : undefined}
          aria-invalid={errors.content ? true : undefined}
          aria-describedby={errors.content ? contentErrorId : undefined}
          onChange={(e) => onPatch({ content: e.target.value }, 'content')}
        />
        {errors.content && (
          <p id={contentErrorId} role="alert" className="field-error">
            {errors.content}
          </p>
        )}
      </div>
    </div>
  )
}
