import type { ReactNode } from 'react'
import { ComboBox, type ComboOption } from '../../../shared/ui/ComboBox'

/** `control` 렌더 함수가 받는 편집 상태(사용자 지정 입력기용). */
export interface InlineControlContext {
  value: string
  onChange: (value: string) => void
  /** 저장. 값을 바로 넘기면 그 값으로 저장한다(목록에서 고른 직후처럼 상태 갱신을 기다릴 수 없을 때). */
  commit: (text?: string) => void
  /** 입력기에 붙일 접근성 이름. */
  inputLabel: string
}

export type InlineKind = 'text' | 'number' | 'date' | 'select' | 'combo' | 'custom'

interface InlineControlProps {
  kind: InlineKind
  name: string
  inputLabel: string
  value: string
  onChange: (value: string) => void
  busy: boolean
  options: readonly ComboOption[]
  /** 입력 문자열 가공(공백 제거 등). 없으면 그대로. */
  sanitize?: (raw: string) => string
  /** 목록에서 고른 즉시 저장. */
  onPick: (option: ComboOption) => void
  commit: (text?: string) => void
  control?: (context: InlineControlContext) => ReactNode
}

/** InlineEdit이 쓰는 입력기: 텍스트·숫자·날짜 input, select, 자동완성 ComboBox, 사용자 지정. */
export function InlineControl(props: InlineControlProps) {
  const { kind, name, inputLabel, value, onChange, busy, options, sanitize, onPick, commit, control } = props
  if (kind === 'custom' && control) return <>{control({ value, onChange, commit, inputLabel })}</>
  if (kind === 'select') {
    return (
      <select aria-label={inputLabel} value={value} onChange={(e) => onChange(e.target.value)} disabled={busy}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label ?? o.value}
          </option>
        ))}
      </select>
    )
  }
  if (kind === 'combo') {
    return (
      <ComboBox
        label={inputLabel}
        name={name}
        value={value}
        onChange={onChange}
        options={options}
        onSelectOption={onPick}
        transform={sanitize}
        disabled={busy}
      />
    )
  }
  const type = kind === 'number' || kind === 'date' ? kind : 'text'
  return (
    <input type={type} aria-label={inputLabel} value={value} onChange={(e) => onChange(sanitize ? sanitize(e.target.value) : e.target.value)} disabled={busy} />
  )
}
