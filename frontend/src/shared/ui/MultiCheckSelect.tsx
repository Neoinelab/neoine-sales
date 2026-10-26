import { useEffect, useId, useRef, useState } from 'react'

interface MultiCheckSelectProps {
  label: string
  name: string
  /** 코드 순서대로. */
  options: readonly { value: string; label: string }[]
  selected: readonly string[]
  /** 버튼에 보이는 선택 요약. */
  summary: string
  onToggle: (value: string, on: boolean) => void
  /** 선택을 모두 지운다. */
  onClear: () => void
}

/** 체크박스 드롭다운. 열림 상태만 갖고 선택은 호출자(URL)가 정한다. Escape(포커스는 버튼으로)·바깥 클릭으로 닫는다. */
export function MultiCheckSelect({ label, name, options, selected, summary, onToggle, onClear }: MultiCheckSelectProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const labelId = useId()
  const buttonId = useId()
  const panelId = useId()

  useEffect(() => {
    if (!open) return
    const close = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      buttonRef.current?.focus()
    }
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', close)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  return (
    <div
      ref={rootRef}
      className="field multi-check"
      onBlur={(event) => {
        // 포커스가 컴포넌트 밖(문서 밖 포함)으로 나가면 닫는다(포커스는 이동한 곳에 둔다). 패널 안 이동은 유지.
        const next = event.relatedTarget as Node | null
        if (!next || !event.currentTarget.contains(next)) setOpen(false)
      }}
    >
      <span id={labelId}>{label}</span>
      <button
        ref={buttonRef}
        type="button"
        id={buttonId}
        className="multi-check-button"
        aria-labelledby={`${labelId} ${buttonId}`}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        {summary}
      </button>
      {open && (
        <div id={panelId} role="group" aria-label={label} className="multi-check-panel" tabIndex={-1}>
          {options.map((o) => (
            <label key={o.value} className="multi-check-option">
              <input type="checkbox" name={name} value={o.value} checked={selected.includes(o.value)} onChange={(e) => onToggle(o.value, e.target.checked)} />
              {o.label}
            </label>
          ))}
          <button type="button" onClick={onClear}>
            전체
          </button>
        </div>
      )}
    </div>
  )
}
