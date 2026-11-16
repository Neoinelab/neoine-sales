/** 계약 목록의 검증·검색·정렬(서버 규칙을 흉내 낸다): 정렬 키마다 값 없는 칸은 방향과 무관하게 맨 뒤, 동률은 id 오름차순. */

import type { ContractStatus, InspectionCycle, LicenseContractQuery, LicenseContractSort } from '../../../shared/model/types'
import { validation } from '../errors'
import type { LicenseContractRecord, SeedData } from '../store'
import { dealSideOf } from './contractViews'

const TEXT_MAX = 200
const INVALID_FORM = '요청 형식이 올바르지 않습니다'

const STATUS_RANK: Record<ContractStatus, number> = { not_issued: 0, issued_new: 1, issued_renewal: 2, ended: 3 }
const INSPECTION_RANK: Record<InspectionCycle, number> = { monthly: 0, quarterly: 1, semiannual: 2, yearly: 3, none: 4 }

export function validateContractQuery(query: LicenseContractQuery): void {
  for (const text of [query.customer, query.product]) {
    if (text !== undefined && Array.from(text).length > TEXT_MAX) throw validation(INVALID_FORM)
  }
  if (query.startFrom && query.startTo && query.startFrom > query.startTo) throw validation('라이선스 시작일 범위의 시작은 끝보다 늦을 수 없습니다.')
  if (query.endFrom && query.endTo && query.endFrom > query.endTo) throw validation('라이선스 종료일 범위의 시작은 끝보다 늦을 수 없습니다.')
}

const includes = (text: string, part: string | undefined): boolean => part === undefined || part.trim() === '' || text.toLowerCase().includes(part.trim().toLowerCase())

/** 양끝 포함, 한쪽만 가능. 날짜 조건이 있으면 날짜 없는 계약은 제외한다. */
function inRange(value: string | null, from: string | undefined, to: string | undefined): boolean {
  if (!from && !to) return true
  if (value === null) return false
  return (!from || value >= from) && (!to || value <= to)
}

export function matchesContract(data: SeedData, record: LicenseContractRecord, query: LicenseContractQuery): boolean {
  const side = dealSideOf(data, record)
  return (
    includes(side.customer, query.customer) &&
    includes(side.product, query.product) &&
    (query.vendorId === undefined || side.vendor?.id === query.vendorId) &&
    (query.ownerId === undefined || side.owner.id === query.ownerId) &&
    (query.status === undefined || record.status === query.status) &&
    inRange(record.licenseStart, query.startFrom, query.startTo) &&
    inRange(record.licenseEnd, query.endFrom, query.endTo)
  )
}

type Key = string | number | null

function keyOf(data: SeedData, record: LicenseContractRecord, sort: LicenseContractSort): Key {
  const side = dealSideOf(data, record)
  // 빈 문자열은 '값 없음'이다(Vendor·파트너 없음, 빈 Product·기술담당·Note).
  const text = (value: string | null): Key => (value === null || value === '' ? null : value.toLowerCase())
  switch (sort) {
    case 'dealName':
      return text(side.dealName)
    case 'customer':
      return text(side.customer)
    case 'vendor':
      return text(side.vendor?.name ?? null)
    case 'product':
      return text(side.product)
    case 'partner':
      return text(side.partner)
    case 'licenseStart':
      return record.licenseStart
    case 'licenseEnd':
      return record.licenseEnd
    case 'status':
      return STATUS_RANK[record.status]
    case 'salesOwner':
      return text(side.owner.name)
    case 'techOwner':
      return text(record.techOwner)
    case 'inspection':
      return INSPECTION_RANK[record.inspection]
    case 'note':
      return text(record.note)
  }
}

export function sortContracts(data: SeedData, rows: LicenseContractRecord[], query: LicenseContractQuery): LicenseContractRecord[] {
  const sign = query.order === 'asc' ? 1 : -1
  const keys = new Map(rows.map((r) => [r.id, keyOf(data, r, query.sort)]))
  return rows.sort((a, b) => {
    const x = keys.get(a.id) ?? null
    const y = keys.get(b.id) ?? null
    if (x === null || y === null) return x === y ? a.id - b.id : x === null ? 1 : -1
    if (x === y) return a.id - b.id
    return (x < y ? -1 : 1) * sign
  })
}
