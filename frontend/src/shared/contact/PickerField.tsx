interface PickerFieldProps {
  label: string
  /** 화면에 보이는 라벨 글자(접근성 이름은 label 유지). */
  visibleLabel?: string
  name: string
  value: string
  onChange: (value: string) => void
  inputMode?: 'text' | 'email' | 'tel'
  error?: string
  /** 오류가 아닌 안내(공백 제거 알림 등). */
  hint?: string
  onBlur?: () => void
}

/** ContactPicker 안의 단순 텍스트 입력. 라벨 연결, 입력 아래 오류(role=alert)/안내. */
export function PickerField({ label, visibleLabel, name, value, onChange, inputMode = 'text', error, hint, onBlur }: PickerFieldProps) {
  return (
    <div className="field">
      <label>
        <span>{visibleLabel ?? label}</span>
        <input
          name={name}
          aria-label={visibleLabel ? label : undefined}
          value={value}
          inputMode={inputMode}
          aria-invalid={error ? true : undefined}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
        />
      </label>
      {error && (
        <p role="alert" className="field-error">
          {error}
        </p>
      )}
      {hint && <p className="field-hint">{hint}</p>}
    </div>
  )
}
