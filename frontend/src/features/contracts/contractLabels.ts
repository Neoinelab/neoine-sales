import type { ContractStatus, InspectionCycle } from '../../shared/model/types'

export const STATUS_LABELS: Record<ContractStatus, string> = { not_issued: '미발급', issued_new: '발급(신규)', issued_renewal: '발급(갱신)', ended: '종료' }

export const INSPECTION_LABELS: Record<InspectionCycle, string> = {
  monthly: '월 1회',
  quarterly: '분기 1회',
  semiannual: '반기 1회',
  yearly: '연 1회',
  none: '없음',
}

export const isIssuedStatus = (status: ContractStatus): boolean => status === 'issued_new' || status === 'issued_renewal'
