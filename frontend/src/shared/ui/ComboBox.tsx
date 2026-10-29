import { useId, useState, type KeyboardEvent, type Ref } from 'react'
import './ui.css'

export interface ComboOption {
  /** 선택하면 입력란에 들어가는 값. */
  value: string
  /** 목록 표시 문구(기본 value). */
  label?: string
  /** 오른쪽 보조 문구(직급·이메일 등). */
  description?: string
  /** 호출처가 선택 결과를 알아보는 데 쓰는 id(예: contactId). */
  id?: number
}

interface ComboBoxProps {
  label: string
  /** 화면에 보이는 라벨 글자(접근성 이름은 label 유지). 없으면 label을 그대로 보인다. */
  visibleLabel?: string
  name: string
  value: string
  /** 직접 입력 또는 선택으로 값이 바뀔 때(transform 적용 후). */
  onChange: (value: string) => void
  options: readonly ComboOption[]
  /** 목록에서 선택했을 때만(직접 입력은 제외). */
  onSelectOption?: (option: ComboOption) => void
  /** 입력 문자열 가공(예: 공백 제거). */
  transform?: (raw: string) => string
  required?: boolean
  disabled?: boolean
  placeholder?: string
  error?: string
  /** 입력 아래 안내(오류 아님). */
  hint?: string
  /** 입력란에 포커스를 옮기려는 호출처용. */
  inputRef?: Ref<HTMLInputElement>
  /** 포커스만으로 목록을 열지(기본 true). false이면 클릭·입력·방향키로 연다(팝업이 열릴 때 첫 칸의 목록이 저절로 열리지 않게). */
  openOnFocus?: boolean
}

/** 목록에서 고르거나 직접 입력하는 콤보박스(ARIA combobox/listbox, 키보드 지원). */
export function ComboBox(props: ComboBoxProps) {
  const { label, visibleLabel, name, value, onChange, options, onSelectOption, transform, required, disabled, placeholder, error, hint, inputRef, openOnFocus = true } = props
  const baseId = useId()
  const listId = `${baseId}-list`
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)

  const typed = value.toLowerCase()
  const exact = options.some((o) => o.value.toLowerCase() === typed)
  const shown = typed && !exact ? options.filter((o) => (o.label ?? o.value).toLowerCase().includes(typed)) : options
  const isOpen = open && shown.length > 0

  function choose(option: ComboOption) {
    onChange(option.value)
    onSelectOption?.(option)
    setOpen(false)
    setActive(-1)
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      if (!isOpen) {
        setOpen(true)
        return
      }
      const step = event.key === 'ArrowDown' ? 1 : -1
      setActive((index) => (index + step + shown.length) % shown.length)
    } else if (event.key === 'Enter' && isOpen && active >= 0) {
      event.preventDefault()
      const option = shown[active]
      if (option) choose(option)
    } else if (event.key === 'Escape' && isOpen) {
      event.stopPropagation()
      setOpen(false)
      setActive(-1)
    }
  }

  return (
    <div className="field combo">
      <label htmlFor={`${baseId}-input`}>{visibleLabel ?? label}</label>
      <input
        id={`${baseId}-input`}
        ref={inputRef}
        name={name}
        aria-label={visibleLabel ? label : undefined}
        role="combobox"
        aria-expanded={isOpen}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={isOpen && active >= 0 ? `${baseId}-opt-${active}` : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${baseId}-error` : undefined}
        autoComplete="off"
        value={value}
        required={required}
        disabled={disabled}
        placeholder={placeholder}
        onFocus={() => openOnFocus && setOpen(true)}
        onClick={() => setOpen(true)}
        onBlur={() => {
          setOpen(false)
          setActive(-1)
        }}
        onChange={(event) => {
          onChange(transform ? transform(event.target.value) : event.target.value)
          setOpen(true)
          setActive(-1)
        }}
        onKeyDown={onKeyDown}
      />
      {isOpen && (
        <ul id={listId} role="listbox" aria-label={label} className="combo-list">
          {shown.map((option, index) => (
            <li
              key={option.id ?? option.value}
              id={`${baseId}-opt-${index}`}
              role="option"
              aria-selected={index === active}
              tabIndex={-1}
              className="combo-option"
              onMouseDown={(event) => {
                event.preventDefault()
                choose(option)
              }}
            >
              <span>{option.label ?? option.value}</span>
              {option.description && <small>{option.description}</small>}
            </li>
          ))}
        </ul>
      )}
      {error && (
        <p id={`${baseId}-error`} role="alert" className="field-error">
          {error}
        </p>
      )}
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  )
}
