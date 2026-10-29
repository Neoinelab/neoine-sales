import type { ChangeEvent, ReactNode } from 'react'
import { DateInput } from './DateInput'

interface BaseProps {
  label: string
  name: string
  required?: boolean
}

export function TextField(
  props: BaseProps & {
    value: string
    onChange: (value: string) => void
    type?: 'text' | 'password' | 'email' | 'tel' | 'number' | 'date' | 'datetime-local'
    /** 브라우저 자동 채움 힌트(`username`, `current-password`, `off` …). 생략하면 브라우저가 정한다. */
    autoComplete?: string
    maxLength?: number
  },
) {
  const { label, name, value, onChange, type = 'text', required, autoComplete, maxLength } = props
  if (type === 'date') {
    return (
      <div className="field">
        <label htmlFor={`${name}-date`}>{label}</label>
        <DateInput id={`${name}-date`} name={name} aria-label={label} value={value} onChange={onChange} required={required} />
      </div>
    )
  }
  return (
    <label className="field">
      <span>{label}</span>
      <input
        name={name}
        type={type}
        value={value}
        required={required}
        autoComplete={autoComplete}
        maxLength={maxLength}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.value)}
      />
    </label>
  )
}

export function TextArea(props: BaseProps & { value: string; onChange: (value: string) => void }) {
  const { label, name, value, onChange, required } = props
  return (
    <label className="field">
      <span>{label}</span>
      <textarea
        name={name}
        value={value}
        required={required}
        rows={3}
        onChange={(e: ChangeEvent<HTMLTextAreaElement>) => onChange(e.target.value)}
      />
    </label>
  )
}

export function SelectField(
  props: BaseProps & {
    value: string
    onChange: (value: string) => void
    children: ReactNode
    disabled?: boolean
  },
) {
  const { label, name, value, onChange, required, children, disabled } = props
  return (
    <label className="field">
      <span>{label}</span>
      <select
        name={name}
        value={value}
        required={required}
        disabled={disabled}
        onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      >
        {children}
      </select>
    </label>
  )
}

export function CheckboxField(props: { label: string; name: string; checked: boolean; onChange: (checked: boolean) => void }) {
  const { label, name, checked, onChange } = props
  return (
    <label className="field checkbox">
      <input
        name={name}
        type="checkbox"
        checked={checked}
        onChange={(e: ChangeEvent<HTMLInputElement>) => onChange(e.target.checked)}
      />
      <span>{label}</span>
    </label>
  )
}
