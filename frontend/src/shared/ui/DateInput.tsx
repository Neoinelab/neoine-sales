import { useEffect, useId, useLayoutEffect, useRef, useState, type FocusEvent, type KeyboardEvent, type RefObject } from 'react'
import { dateParseError, dateTextToValue, finalizeDateText, formatDateTyping, isDateValue, isoToDateText, parseDateText } from '../model/dateText'

export interface DateInputProps {
  /** 'YYYY-MM-DD' | '' | 입력 중 글자(틀린 글자는 그대로 올라온다). */
  value: string
  onChange: (next: string) => void
  id?: string
  name?: string
  'aria-label'?: string
  'aria-describedby'?: string
  /** 부모 검증 문구. 자체 오류가 없을 때 보인다. */
  error?: string
  /** 부모가 문구를 따로 보이는 화면용: 자체 문구와 `aria-invalid`를 내지 않는다(`invalid`로 부모가 켠다). */
  quiet?: boolean
  invalid?: boolean
  disabled?: boolean
  required?: boolean
  inputRef?: ((el: HTMLInputElement | null) => unknown) | RefObject<HTMLInputElement | null>
  /** Enter를 눌렀을 때(글자를 확정한 뒤). 주면 폼 기본 동작을 막는다. */
  onEnter?: (value: string) => void
  /** 달력에서 날짜를 골랐을 때. */
  onPicked?: (value: string) => void
  /** 텍스트 칸을 벗어났을 때(글자 확정 뒤). 포커스가 갈 곳은 `relatedTarget`. */
  onBlur?: (event: FocusEvent<HTMLInputElement>) => void
  /** 텍스트 칸의 키 입력(Esc 취소 등). Enter 처리보다 먼저 불린다. */
  onKeyDown?: (event: KeyboardEvent<HTMLInputElement>) => void
  autoFocus?: boolean
  className?: string
}

function assignRef(ref: DateInputProps['inputRef'], el: HTMLInputElement | null) {
  if (typeof ref === 'function') ref(el)
  else if (ref) ref.current = el
}

/** yyyymmdd를 키보드로 치면 yyyy.mm.dd로 보이고, 달력으로도 고르는 날짜 입력 칸. 날짜 입력은 이 컴포넌트만 쓴다. */
export function DateInput(props: DateInputProps) {
  const { value, onChange, id, name, error, quiet, invalid, disabled, required, inputRef, onEnter, onPicked, onBlur, onKeyDown, autoFocus, className } = props
  const ariaLabel = props['aria-label']
  const [text, setText] = useState(() => isoToDateText(value))
  const [prevValue, setPrevValue] = useState(value)
  const [touched, setTouched] = useState(false)
  const textRef = useRef<HTMLInputElement | null>(null)
  const nativeRef = useRef<HTMLInputElement | null>(null)
  const errorId = useId()
  // 글자를 다시 만든 뒤에도 캐럿이 입력한 자리(캐럿 앞 숫자 개수)에 남게 한다.
  const caretDigits = useRef<number | 'end' | null>(null)
  const [, setTick] = useState(0)
  useLayoutEffect(() => {
    const el = textRef.current
    const digits = caretDigits.current
    caretDigits.current = null
    if (!el || digits === null || document.activeElement !== el) return
    if (digits === 'end') {
      el.setSelectionRange(el.value.length, el.value.length)
      return
    }
    let pos = 0
    let seen = 0
    while (seen < digits && pos < el.value.length) {
      if (/\d/.test(el.value.charAt(pos))) seen += 1
      pos += 1
    }
    el.setSelectionRange(pos, pos)
  })
  // 바깥 <label>로 이름을 받는 칸은 그 글자를 달력 버튼 이름에 쓴다.
  const [outsideName, setOutsideName] = useState('')
  useEffect(() => {
    const found = textRef.current?.labels?.[0]?.textContent?.trim() ?? ''
    setOutsideName(found)
  }, [])

  if (value !== prevValue) {
    setPrevValue(value)
    if (dateTextToValue(text) !== value) setText(isoToDateText(value))
  }

  const parsed = parseDateText(text)
  const ownError = touched && !quiet ? dateParseError(parsed) : null
  const shown = ownError ?? error ?? null
  const describedBy = [props['aria-describedby'], shown ? errorId : undefined].filter(Boolean).join(' ') || undefined
  const nativeValue = parsed.kind === 'valid' ? parsed.iso : ''

  const commit = (): string => {
    const finalText = finalizeDateText(text)
    const next = dateTextToValue(finalText)
    if (finalText !== text) setText(finalText)
    if (next !== value) onChange(next)
    setTouched(true)
    return next
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    onKeyDown?.(e)
    if (e.key !== 'Enter' || e.nativeEvent.isComposing) return
    const next = commit()
    if (onEnter) {
      e.preventDefault()
      onEnter(next)
    }
  }

  const openCalendar = () => {
    const native = nativeRef.current
    if (!native) return
    try {
      if (typeof native.showPicker !== 'function') throw new Error('showPicker unsupported')
      native.showPicker()
    } catch {
      native.focus()
      native.click()
    }
  }

  const accessibleName = ariaLabel ?? outsideName
  const label = accessibleName ? `${accessibleName} 달력 열기` : '달력 열기'

  return (
    <span className={['date-input', className].filter(Boolean).join(' ')}>
      <input
        ref={(el) => {
          textRef.current = el
          assignRef(inputRef, el)
        }}
        id={id}
        name={name}
        type="text"
        inputMode="numeric"
        placeholder="yyyymmdd"
        autoComplete="off"
        value={text}
        disabled={disabled}
        required={required}
        aria-label={ariaLabel}
        aria-describedby={describedBy}
        aria-invalid={shown || invalid ? true : undefined}
        data-autofocus={autoFocus ? '' : undefined}
        onChange={(e) => {
          const raw = e.target.value
          const caret = e.target.selectionStart ?? raw.length
          caretDigits.current = caret >= raw.length ? 'end' : (raw.slice(0, caret).match(/\d/g) ?? []).length
          setTick((n) => n + 1)
          const nextText = formatDateTyping(raw)
          setText(nextText)
          setTouched(false)
          const next = dateTextToValue(nextText)
          if (next !== value) onChange(next)
        }}
        onKeyDown={handleKeyDown}
        onBlur={(e) => {
          commit()
          onBlur?.(e)
        }}
      />
      <button type="button" className="date-input-button" aria-label={label} disabled={disabled} onMouseDown={(e) => e.preventDefault()} onClick={openCalendar}>
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" focusable="false">
          <path d="M3 2.5h10A1.5 1.5 0 0 1 14.5 4v9a1.5 1.5 0 0 1-1.5 1.5H3A1.5 1.5 0 0 1 1.5 13V4A1.5 1.5 0 0 1 3 2.5Zm-.5 4v6.5a.5.5 0 0 0 .5.5h10a.5.5 0 0 0 .5-.5V6.5h-11ZM4.5 1h1v2h-1V1Zm6 0h1v2h-1V1Z" fill="currentColor" />
        </svg>
      </button>
      <input
        ref={nativeRef}
        type="date"
        className="date-input-native"
        tabIndex={-1}
        aria-hidden="true"
        min="1900-01-01"
        max="2999-12-31"
        value={nativeValue}
        disabled={disabled}
        onChange={(e) => {
          const picked = e.target.value
          if (picked !== '' && !isDateValue(picked)) return
          setText(isoToDateText(picked))
          setTouched(false)
          onChange(picked)
          textRef.current?.focus()
          onPicked?.(picked)
        }}
      />
      {shown && (
        <p id={errorId} role="alert" className="field-error">
          {shown}
        </p>
      )}
    </span>
  )
}
