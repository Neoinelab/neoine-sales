import type { SortOrder } from '../../shared/model/inputs'
import type { ContractStatus, LicenseContractQuery, LicenseContractSort } from '../../shared/model/types'

/** 화면의 검색 입력값. Vendor·담당영업은 선택한 id(없으면 ''), 날짜는 'YYYY-MM-DD' 또는 ''. */
export interface ContractConditions {
  customer: string
  vendor: string
  product: string
  salesOwner: string
  status: '' | ContractStatus
  startFrom: string
  startTo: string
  endFrom: string
  endTo: string
}

export const NO_CONTRACT_CONDITIONS: ContractConditions = {
  customer: '',
  vendor: '',
  product: '',
  salesOwner: '',
  status: '',
  startFrom: '',
  startTo: '',
  endFrom: '',
  endTo: '',
}

export type ContractSort = LicenseContractSort

/** 검색 입력값 -> 서버 조건. 비어 있는 조건은 담지 않는다. 필터링과 정렬은 서버가 한다. */
export function toContractQuery(conditions: ContractConditions, sort: ContractSort, order: SortOrder): LicenseContractQuery {
  const query: LicenseContractQuery = { sort, order }
  const customer = conditions.customer.trim()
  const product = conditions.product.trim()
  if (customer) query.customer = customer
  if (product) query.product = product
  if (conditions.vendor) query.vendorId = Number(conditions.vendor)
  if (conditions.salesOwner) query.ownerId = Number(conditions.salesOwner)
  if (conditions.status) query.status = conditions.status
  if (conditions.startFrom) query.startFrom = conditions.startFrom
  if (conditions.startTo) query.startTo = conditions.startTo
  if (conditions.endFrom) query.endFrom = conditions.endFrom
  if (conditions.endTo) query.endTo = conditions.endTo
  return query
}
