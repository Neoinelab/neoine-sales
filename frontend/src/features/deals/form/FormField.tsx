import { useId } from 'react'

interface FormFieldProps {
  label: string
  name: string
  value: string
  onChange: (value: string) => void
  /** 제출 검증 오류. 입력 아래 role=alert로 보이고 aria-invalid가 켜진다. */
  error?: string
  hint?: string
  type?: 'text' | 'date'
  inputMode?: 'text' | 'numeric'
  /** 필수 표시(`*`)는 CSS가 붙인다. 라벨 텍스트에는 들어가지 않는다. */
  required?: boolean
  multiline?: boolean
}

/** 라벨·입력·오류·안내를 묶은 폼 입력. 네이티브 검증은 쓰지 않고 `error`로 문구를 보인다. */
export function FormField({ label, name, value, onChange, error, hint, type = 'text', inputMode, required, multiline }: FormFieldProps) {
  const id = useId()
  const errorId = `${id}-error`
  const common = {
    id,
    name,
    value,
    'aria-invalid': error ? true : undefined,
    'aria-describedby': error ? errorId : undefined,
  }
  return (
    <div className={required ? 'field required' : 'field'}>
      <label htmlFor={id}>{label}</label>
      {multiline ? (
        <textarea {...common} rows={3} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input {...common} type={type} inputMode={inputMode} onChange={(e) => onChange(e.target.value)} />
      )}
      {error && (
        <p id={errorId} role="alert" className="field-error">
          {error}
        </p>
      )}
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  )
}
