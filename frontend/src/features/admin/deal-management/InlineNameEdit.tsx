import { useCallback, type KeyboardEvent } from 'react'

interface Props {
  /** 입력의 접근성 이름(예: '코드 이름', 'Label 이름'). */
  readonly label: string
  readonly name: string
  readonly editing: boolean
  readonly busy: boolean
  readonly onEdit: () => void
  readonly onSave: (name: string) => void
  readonly onCancel: () => void
}

/** 표 안에서 이름만 고치는 인라인 입력. Enter=저장, Esc=취소. 값 검증은 서버의 문구를 그대로 보여준다. */
export function InlineNameEdit({ label, name, editing, busy, onEdit, onSave, onCancel }: Props) {
  const focusInput = useCallback((input: HTMLInputElement | null) => input?.focus(), [])

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.nativeEvent.isComposing || (event.key !== 'Enter' && event.key !== 'Escape')) return
    event.preventDefault()
    if (busy || event.repeat) return
    if (event.key === 'Enter') onSave(event.currentTarget.value)
    else onCancel()
  }

  if (!editing) {
    return (
      <button type="button" className="admin-name-edit" disabled={busy} onClick={onEdit}>
        {name}
      </button>
    )
  }

  return (
    <input
      className="admin-name-input"
      aria-label={label}
      defaultValue={name}
      ref={focusInput}
      readOnly={busy}
      onKeyDown={onKeyDown}
      onBlur={() => {
        if (!busy) onCancel()
      }}
    />
  )
}
