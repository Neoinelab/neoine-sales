import type { RefObject } from 'react'
import { DateInput } from '../../shared/ui/DateInput'
import { licenseDays } from './licenseDraft'

interface LicenseFieldsProps {
  start: string
  end: string
  disabled: boolean
  startError?: string
  endError?: string
  startRef: RefObject<HTMLInputElement | null>
  onChange: (patch: { start?: string; end?: string }) => void
}

export function LicenseFields({ start, end, disabled, startError, endError, startRef, onChange }: LicenseFieldsProps) {
  const days = licenseDays(start, end)
  return (
    <div className="contract-license-fields">
      <div className="contract-license-grid">
        <div className="field">
          <label htmlFor="license-start">라이선스 시작일</label>
          <DateInput id="license-start" inputRef={startRef} value={start} disabled={disabled} error={startError} onChange={(next) => onChange({ start: next })} />
        </div>
        <div className="field">
          <label htmlFor="license-end">라이선스 종료일</label>
          <DateInput id="license-end" value={end} disabled={disabled} error={endError} onChange={(next) => onChange({ end: next })} />
        </div>
      </div>
      <div className="contract-license-end">
        <span className="contract-edit-label">라이선스 유지 기간</span>
        <span>{days === null ? '-' : `${days}일 (종료일 포함)`}</span>
      </div>
    </div>
  )
}
