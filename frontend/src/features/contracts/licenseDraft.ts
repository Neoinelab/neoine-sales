import { dateValueError, isDateValue } from '../../shared/model/dateText'
import type { LicenseContract } from '../../shared/model/types'
import { licenseEnd, nextDayOf, type PeriodUnit } from './licensePeriod'

/** 수정 대화상자 안의 라이선스 입력값. mode가 null이면 읽기 전용(현재 값)이다. */
export type LicenseMode = 'issue' | 'renew'

export interface LicenseDraft {
  mode: LicenseMode
  start: string
  amount: string
  unit: PeriodUnit
}

/** 버튼을 눌렀을 때의 기본값: 발급은 오늘부터 1년, 갱신은 현재 종료일 다음 날부터 현재 기간(없으면 1년). */
export function startLicenseDraft(contract: LicenseContract, mode: LicenseMode, today: string): LicenseDraft {
  const term = contract.term ?? { amount: 1, unit: 'year' as const }
  const start = mode === 'renew' && contract.licenseEnd ? nextDayOf(contract.licenseEnd) : today
  return { mode, start, amount: String(term.amount), unit: term.unit }
}

/** 평소(버튼 전)에 읽기 전용으로 보이는 현재 값. 미발급은 시작일이 빈 칸, 기간 기본 1년. */
export function currentLicenseValues(contract: LicenseContract): Omit<LicenseDraft, 'mode'> {
  const term = contract.term ?? { amount: 1, unit: 'year' as const }
  const start = contract.status === 'not_issued' ? '' : (contract.licenseStart ?? '')
  return { start, amount: String(term.amount), unit: term.unit }
}

export function parseAmount(amount: string): number | null {
  const count = Number(amount)
  return amount !== '' && Number.isInteger(count) && count >= 1 && count <= 99 ? count : null
}

/** 입력값이 올바르면 종료일, 아니면 null. */
export function draftEnd(draft: Pick<LicenseDraft, 'start' | 'amount' | 'unit'>): string | null {
  const count = parseAmount(draft.amount)
  return isDateValue(draft.start) && count !== null ? licenseEnd(draft.start, count, draft.unit) : null
}

export function startError(start: string): string | undefined {
  return start === '' ? '라이선스 시작일을 입력하세요.' : (dateValueError(start) ?? undefined)
}
