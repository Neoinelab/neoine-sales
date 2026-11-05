import type { RefObject } from 'react'
import { DateInput } from '../../shared/ui/DateInput'
import { PERIOD_UNIT_LABELS, type PeriodUnit } from './licensePeriod'

interface LicenseFieldsProps {
  start: string
  amount: string
  unit: PeriodUnit
  /** 시작일 + 기간으로 계산한 종료일. 계산할 수 없으면 null. */
  end: string | null
  disabled: boolean
  startError?: string
  amountError?: string
  startRef: RefObject<HTMLInputElement | null>
  onChange: (patch: { start?: string; amount?: string; unit?: PeriodUnit }) => void
}

const UNITS = Object.keys(PERIOD_UNIT_LABELS) as PeriodUnit[]

/** 계약 수정 대화상자의 라이선스 시작일·기간·기간 단위 칸과 종료일 미리보기. */
export function LicenseFields({ start, amount, unit, end, disabled, startError, amountError, startRef, onChange }: LicenseFieldsProps) {
  return (
    <div className="contract-license-fields">
      <div className="contract-license-grid">
        <div className="field">
          <label htmlFor="license-start">라이선스 시작일</label>
          <DateInput id="license-start" inputRef={startRef} value={start} disabled={disabled} error={startError} onChange={(next) => onChange({ start: next })} />
        </div>
        <label className="field">
          <span>기간</span>
          <input type="number" min={1} max={99} step={1} value={amount} disabled={disabled} onChange={(e) => onChange({ amount: e.target.value })} />
        </label>
        <label className="field">
          <span>기간 단위</span>
          <select value={unit} disabled={disabled} onChange={(e) => onChange({ unit: e.target.value as PeriodUnit })}>
            {UNITS.map((u) => (
              <option key={u} value={u}>
                {PERIOD_UNIT_LABELS[u]}
              </option>
            ))}
          </select>
        </label>
      </div>
      {amountError && (
        <p role="alert" className="error">
          {amountError}
        </p>
      )}
      <p className="hint">종료일 {end === null ? '-' : end}</p>
    </div>
  )
}
