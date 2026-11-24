import { dateValueError, isDateValue } from '../../shared/model/dateText'
import type { LicenseContract } from '../../shared/model/types'
import { licenseEnd, nextDayOf } from './licensePeriod'

export type LicenseMode = 'issue' | 'renew'

export interface LicenseDraft {
  mode: LicenseMode
  start: string
  end: string
}

export function startLicenseDraft(contract: LicenseContract, mode: LicenseMode, today: string): LicenseDraft {
  const start = mode === 'renew' && contract.licenseEnd ? nextDayOf(contract.licenseEnd) : today
  if (mode === 'renew' && contract.licenseStart && contract.licenseEnd) {
    const duration = Date.parse(`${contract.licenseEnd}T00:00:00Z`) - Date.parse(`${contract.licenseStart}T00:00:00Z`)
    const end = contract.term
      ? licenseEnd(start, contract.term.amount, contract.term.unit)
      : new Date(Date.parse(`${start}T00:00:00Z`) + duration).toISOString().slice(0, 10)
    return { mode, start, end }
  }
  return { mode, start, end: licenseEnd(start, 1, 'year') }
}

export function currentLicenseValues(contract: LicenseContract): Omit<LicenseDraft, 'mode'> {
  return { start: contract.licenseStart ?? '', end: contract.licenseEnd ?? '' }
}

export function startError(start: string): string | undefined {
  return start === '' ? '라이선스 시작일을 입력하세요.' : (dateValueError(start) ?? undefined)
}

export function endError(start: string, end: string): string | undefined {
  if (end === '') return '라이선스 종료일을 입력하세요.'
  const error = dateValueError(end)
  if (error) return error
  if (isDateValue(start) && end < start) return '라이선스 종료일은 시작일보다 빠를 수 없습니다.'
  return undefined
}

export function licenseDays(start: string, end: string): number | null {
  if (startError(start) || endError(start, end)) return null
  return Math.round((Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000) + 1
}
