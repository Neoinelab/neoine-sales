import { addMonthsClamped } from './licensePeriod'
import type { ContractStatus } from '../../shared/model/types'

export type ExpiryLevel = 'danger' | 'warning'

export const EXPIRY_TITLES: Record<ExpiryLevel, string> = { danger: '만료 1개월 미만', warning: '만료 2개월 미만' }

/** 발급 상태 계약의 만료 임박 단계: 종료일 < 오늘+1개월이면 danger(지난 날 포함), < 오늘+2개월이면 warning. */
export function expiryLevel(end: string | null, status: ContractStatus, today: string): ExpiryLevel | null {
  if ((status !== 'issued_new' && status !== 'issued_renewal') || end === null) return null
  if (end < addMonthsClamped(today, 1)) return 'danger'
  if (end < addMonthsClamped(today, 2)) return 'warning'
  return null
}
