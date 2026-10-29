import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type Ref } from 'react'
import { usePartnerDealOptions } from '../../data/partnerMeetings'
import { isDateValue } from '../../shared/model/dateText'
import { ComboBox, type ComboOption } from '../../shared/ui/ComboBox'
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
  /** 없으면 "행 삭제" 버튼을 두지 않는다(수정 팝업). */
  onRemove?: () => void
  removeDisabled?: boolean
  /** 내용 칸의 키 입력(Enter 처리는 팝업이 한다). */
  onContentKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void
  /** 열릴 때 내용 칸에 포커스를 둔다(수정 팝업). */
  autoFocusContent?: boolean
}

const NOT_LISTED = '목록에서 선택하세요.'

function dealValue(name: string, code: string): string {
  return `${name} [${code}]`
}

/** 입력 팝업의 한 행: 파트너 -> Deal -> 미팅 날짜 -> 미팅 내용. 칸 이동은 선택·Enter로 이어진다. */
export function MeetingEntryRow(props: MeetingEntryRowProps) {
  const { number, row, errors, companies, focusField, onFocused, onPatch, onRemove, removeDisabled, onContentKeyDown, autoFocusContent } = props
  const partnerRef = useRef<HTMLInputElement>(null)
  const dealRef = useRef<HTMLInputElement>(null)
  const dateRef = useRef<HTMLInputElement>(null)
  const contentRef = useRef<HTMLTextAreaElement>(null)
  const dateId = useId()
  const contentId = useId()
  const contentErrorId = `${contentId}-error`
  const options = usePartnerDealOptions(row.partnerCompany).data
  // 파트너를 목록에서 고른 직후에만, 고른 Deal이 새 회사의 선택지에 없으면 비운다(저장된 Deal을 그대로 두는 수정 팝업을 지키기 위해).
  const verifyFor = useRef<string | null>(null)
  // 파트너를 고르면 Deal 칸이 켜진 다음에 포커스를 옮겨야 하므로 렌더 뒤에 처리한다(선택 핸들러가 행 상태도 바꾸므로 반드시 다시 그려진다).
  const ownFocus = useRef<EntryField | null>(null)
  // 글자를 쳐 Enter를 눌렀지만 목록에 같은 항목이 없을 때의 안내(해당 칸).
  const [notListed, setNotListed] = useState<'partnerCompany' | 'dealCode' | null>(null)

  const dealOptions = useMemo<ComboOption[]>(
    () => (options ?? []).map((o) => ({ value: dealValue(o.name, o.code), description: o.customerCompany })),
    [options],
  )
  const dealCodeOfValue = useMemo(() => new Map((options ?? []).map((o) => [dealValue(o.name, o.code), o.code])), [options])

  useEffect(() => {
    const wanted = focusField ?? ownFocus.current
    if (!wanted) return
    ownFocus.current = null
    const target = { partnerCompany: partnerRef, dealCode: dealRef, meetingDate: dateRef, content: contentRef }[wanted]
    target.current?.focus()
    if (focusField) onFocused()
  })

  useEffect(() => {
    if (verifyFor.current === null || verifyFor.current !== row.partnerCompany || options === undefined) return
    verifyFor.current = null
    if (row.dealCode !== '' && !options.some((o) => o.code === row.dealCode)) onPatch({ dealText: '', dealCode: '' })
  }, [row.partnerCompany, row.dealCode, options, onPatch])

  /** 닫힌 목록(또는 활성 항목 없는 목록)에서 Enter는 다음 칸으로. 목록의 활성 항목 선택은 ComboBox가 먼저 처리한다. */
  function moveOnWithEnter(event: KeyboardEvent<HTMLDivElement>, next: () => void) {
    if (event.key !== 'Enter' || event.isDefaultPrevented() || event.nativeEvent.isComposing) return
    event.preventDefault()
    next()
  }

  function choosePartner(company: string) {
    onPatch({ partnerText: company, partnerCompany: company }, 'partnerCompany')
    verifyFor.current = company
    ownFocus.current = 'dealCode'
    setNotListed(null)
  }

  function chooseDeal(value: string) {
    onPatch({ dealText: value, dealCode: dealCodeOfValue.get(value) ?? '' }, 'dealCode')
    dateRef.current?.focus()
    setNotListed(null)
  }

  /** 목록 글자와 정확히 같은 글자(대소문자·앞뒤 공백 무시)는 목록에서 고른 것으로 본다. */
  function sameText(a: string, b: string): boolean {
    return a.trim().toLowerCase() === b.trim().toLowerCase()
  }

  function enterOnPartner() {
    if (row.partnerText.trim() === '') {
      if (row.partnerCompany !== '') dealRef.current?.focus()
      return
    }
    const match = companies.find((c) => sameText(c, row.partnerText))
    if (match) choosePartner(match)
    else setNotListed('partnerCompany')
  }

  function enterOnDeal() {
    if (row.dealText.trim() === '') {
      dateRef.current?.focus()
      return
    }
    const match = dealOptions.find((o) => sameText(o.value, row.dealText))
    if (match) chooseDeal(match.value)
    else setNotListed('dealCode')
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
          error={errors.partnerCompany ?? (notListed === 'partnerCompany' ? NOT_LISTED : undefined)}
          onChange={(text) => {
            setNotListed(null)
            onPatch({ partnerText: text, partnerCompany: '' }, 'partnerCompany')
          }}
          onSelectOption={(option) => choosePartner(option.value)}
        />
      </div>
      <div role="presentation" className="meeting-entry-cell" onKeyDown={(e) => moveOnWithEnter(e, enterOnDeal)}>
        <ComboBox
          label="Deal"
          name={`deal-${row.key}`}
          value={row.dealText}
          options={dealOptions}
          disabled={row.partnerCompany === ''}
          inputRef={dealRef as Ref<HTMLInputElement>}
          error={errors.dealCode ?? (notListed === 'dealCode' ? NOT_LISTED : undefined)}
          onChange={(text) => {
            setNotListed(null)
            onPatch({ dealText: text, dealCode: '' }, 'dealCode')
          }}
          onSelectOption={(option) => chooseDeal(option.value)}
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
          rows={2}
          value={row.content}
          data-autofocus={autoFocusContent ? '' : undefined}
          aria-invalid={errors.content ? true : undefined}
          aria-describedby={errors.content ? contentErrorId : undefined}
          onChange={(e) => onPatch({ content: e.target.value }, 'content')}
          onKeyDown={onContentKeyDown}
        />
        {errors.content && (
          <p id={contentErrorId} role="alert" className="field-error">
            {errors.content}
          </p>
        )}
      </div>
      {onRemove && (
        <button type="button" className="meeting-entry-remove" disabled={removeDisabled} onClick={onRemove}>
          행 삭제
        </button>
      )}
    </div>
  )
}
