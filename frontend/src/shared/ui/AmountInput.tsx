import { useLayoutEffect, useReducer, useRef } from 'react'
import type { ChangeEvent, InputHTMLAttributes } from 'react'
import { formatAmountInput } from '../model/money'

type AmountInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'value' | 'onChange' | 'type' | 'inputMode'> & {
  /** 콤마 포함 표시 문자열. */
  value: string
  /** 콤마를 다시 넣은 문자열을 넘긴다. */
  onChange: (text: string) => void
}

/** 천원 단위 금액 입력: 숫자와 콤마만 남기고 입력 중 콤마를 넣으며 커서를 유지한다. */
export function AmountInput({ value, onChange, ...rest }: AmountInputProps) {
  const ref = useRef<HTMLInputElement>(null)
  const caretRef = useRef<number | null>(null)
  const [, forceRender] = useReducer((n: number) => n + 1, 0)

  useLayoutEffect(() => {
    const input = ref.current
    if (caretRef.current !== null && input && document.activeElement === input) {
      input.setSelectionRange(caretRef.current, caretRef.current)
    }
    caretRef.current = null
  })

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value
    const next = formatAmountInput(raw, e.target.selectionStart ?? raw.length)
    caretRef.current = next.caret
    // 정리 결과가 현재 값과 같으면 부모가 다시 렌더하지 않으므로 직접 렌더해 커서를 되돌린다.
    onChange(next.text)
    if (next.text === value) forceRender()
  }

  return <input {...rest} ref={ref} type="text" inputMode="numeric" value={value} onChange={handleChange} />
}
