/** 라이선스 계약(계약관리) 모델과 입력. 계약은 Deal이 Won이 될 때 서버가 만들며, Deal에서 오는 5칸(고객사·Vendor·제품·파트너사·담당영업)은 읽기 전용이다. */

import type { SortOrder } from './inputs'
import type { NamedRef, UserRef } from './types'

export type ContractStatus = 'not_issued' | 'issued_new' | 'issued_renewal' | 'ended'
export type InspectionCycle = 'monthly' | 'quarterly' | 'semiannual' | 'yearly' | 'none'
export type TermUnit = 'month' | 'year'

export interface LicenseTerm {
  /** 1~99. */
  amount: number
  unit: TermUnit
}

export interface LicenseContract {
  id: number
  dealCode: string
  dealName: string
  customer: string
  vendor: NamedRef | null
  product: string
  partner: string | null
  salesOwner: UserRef
  /** 계약의 Deal이 Won인가. 아니면 발급·갱신할 수 없다. */
  dealIsWon: boolean
  status: ContractStatus
  /** 'YYYY-MM-DD'. 미발급은 null. */
  licenseStart: string | null
  licenseEnd: string | null
  term: LicenseTerm | null
  techOwner: string
  inspection: InspectionCycle
  note: string
  renewedFromId: number | null
  endedOn: string | null
  attachmentCount: number
  createdBy: UserRef
  updatedBy: UserRef
  createdAt: string
  updatedAt: string
}

export type LicenseContractSort =
  | 'dealName'
  | 'customer'
  | 'vendor'
  | 'product'
  | 'partner'
  | 'licenseStart'
  | 'licenseEnd'
  | 'status'
  | 'salesOwner'
  | 'techOwner'
  | 'inspection'
  | 'note'

/** 검색 조건. 고객사명·제품명은 Deal 값의 부분 일치, Vendor·담당영업은 id 일치, 날짜는 양끝 포함. */
export interface LicenseContractQuery {
  customer?: string
  product?: string
  vendorId?: number
  ownerId?: number
  status?: ContractStatus
  startFrom?: string
  startTo?: string
  endFrom?: string
  endTo?: string
  sort: LicenseContractSort
  order: SortOrder
}

/** 계약 자체 칸(수정). 고객사명 등 Deal 값은 보내지 않는다. */
export interface LicenseContractFields {
  techOwner: string
  inspection: InspectionCycle
  note: string
}

export type LicenseIssueInput = LicenseContractFields & {
  start: string
} & ({ end: string; term?: never } | { term: LicenseTerm; end?: never })

/** 계약 첨부 한 건. Deal 첨부와 같은 모양이며 Deal 대신 계약에 속한다. */
export interface ContractAttachment {
  id: number
  contractId: number
  dealCode: string
  fileName: string
  size: number
  mime: string
  description: string
  uploadedBy: UserRef
  uploadedAt: string
}
