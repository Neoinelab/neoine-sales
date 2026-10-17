import { useState, type KeyboardEvent } from 'react'

interface Props {
  /** 입력의 접근성 이름(예: '코드 이름', 'Label 이름'). */
  label: string
  initial: string
  busy?: boolean
  onSave: (name: string) => void
  onCancel: () => void
}

/** 표 안에서 이름만 고치는 인라인 입력. Enter=저장, Esc=취소. 값 검증은 서버의 문구를 그대로 보여준다. */
export function InlineNameEdit({ label, initial, busy = false, onSave, onCancel }: Props) {
  const [name, setName] = useState(initial)
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== 'Escape') return
    event.preventDefault()
    onCancel()
  }
  return (
    <form
      className="inline-edit"
      onSubmit={(e) => {
        e.preventDefault()
        onSave(name)
      }}
    >
      <input
        aria-label={label}
        value={name}
        // 수정 버튼을 눌러 연 직후 바로 입력할 수 있게 한다.
        // eslint-disable-next-line jsx-a11y/no-autofocus
        autoFocus
        onChange={(e) => setName(e.target.value)}
        onKeyDown={onKeyDown}
      />
      <button type="submit" className="small primary" disabled={busy}>
        저장
      </button>
      <button type="button" className="small" onClick={onCancel}>
        취소
      </button>
    </form>
  )
}
