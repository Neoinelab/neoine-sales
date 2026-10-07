import type { ChangeEvent, ReactNode } from 'react'

interface BaseProps {
  label: string
  name: string
  required?: boolean
}

export function TextField(
  props: BaseProps & {
    value: string
    onChange: (value: string) => void
    type?: 'text' | 'email' | 'tel' | 'number' | 'date' | 'datetime-local'
  },
) {
  const { label, name, value, onChange, type = 'text', required } = props
  return (
    <label className="field">
      <span>{label}</span>
      <input
        name={name}
        type={type}
        value={value}
        required={required}
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
  },
) {
  const { label, name, value, onChange, required, children } = props
  return (
    <label className="field">
      <span>{label}</span>
      <select
        name={name}
        value={value}
        required={required}
        onChange={(e: ChangeEvent<HTMLSelectElement>) => onChange(e.target.value)}
      >
        {children}
      </select>
    </label>
  )
}
