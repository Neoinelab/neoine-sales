import { useLayoutEffect, useRef, type KeyboardEvent } from 'react'

interface AutoGrowTextAreaProps {
  label: string
  value: string
  onChange: (value: string) => void
  /** 여는 순간 값 버튼 높이(px). 0이면 못 쟀다는 뜻이라 3줄로 연다. */
  startHeight: number
  disabled?: boolean
}

/** 값 버튼 높이로 시작해 내용이 넘치면 늘어나는 여러 줄 칸(줄어들어도 시작 높이 아래로는 내려가지 않는다). Enter 동작은 InlineEdit이 정한다(saveButtons 칸은 Enter·Shift+Enter 모두 줄바꿈, 아니면 Enter 저장·Shift+Enter 줄바꿈). */
export function AutoGrowTextArea({ label, value, onChange, startHeight, disabled = false }: AutoGrowTextAreaProps) {
  const ref = useRef<HTMLTextAreaElement>(null)
  /** 마지막으로 이 컴포넌트가 정한 높이(px). 이것과 다르면 사용자가 끌어서 바꾼 높이다. */
  const autoHeight = useRef(startHeight)
  /** 사용자가 끌어서 늘린 높이(px). 내용이 줄어도 이 아래로는 줄이지 않는다. */
  const userHeight = useRef(0)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || startHeight <= 0) return
    const shown = Number.parseFloat(el.style.height)
    if (Number.isFinite(shown) && shown !== autoHeight.current && shown > startHeight) userHeight.current = shown
    el.style.height = `${startHeight}px`
    const content = el.scrollHeight
    const next = Math.max(userHeight.current, content > startHeight ? content + 2 : startHeight)
    el.style.height = `${next}px`
    autoHeight.current = next
  }, [value, startHeight])
  return (
    <textarea
      ref={ref}
      className="dd-fill-text"
      aria-label={label}
      value={value}
      disabled={disabled}
      rows={startHeight > 0 ? undefined : 3}
      style={startHeight > 0 ? { height: `${startHeight}px` } : undefined}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={(e: KeyboardEvent) => {
        if (e.key === 'Enter' && e.shiftKey) e.stopPropagation()
      }}
    />
  )
}
