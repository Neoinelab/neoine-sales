/**
 * 계약관리 화면·Fake 테스트 공용 도구(운영 코드에서 쓰지 않는다).
 *
 * 계약 데이터는 Fake 게이트웨이(`gateway.licenseContracts`)가 가진다. 화면 테스트의 기대값은 시안 상수가 아니라
 * 이 도구로 게이트웨이에서 읽은 값으로 계산한다. 도구는 모두 admin(root)으로 읽는다(화면이 다시 로그인한다).
 *
 * 게이트웨이 계약(구현자가 맞춘다, shared/model/types.ts)
 *   LicenseContract { id, dealCode, dealName, customer, vendor: NamedRef | null, product, partner: string | null,
 *     salesOwner: UserRef, status: ContractStatus, licenseStart: string | null, licenseEnd: string | null,
 *     term: { amount: number; unit: 'month' | 'year' } | null, techOwner, inspection: InspectionCycle, note,
 *     renewedFromId: number | null, endedOn: string | null, attachmentCount: number,
 *     createdBy: UserRef, updatedBy: UserRef, createdAt, updatedAt }
 *   LicenseContractQuery { customer?, product?, vendorId?, ownerId?, status?, startFrom?, startTo?, endFrom?, endTo?,
 *     sort: LicenseContractSort, order: SortOrder }
 *   LicenseContractSort = 'dealName' | 'customer' | 'vendor' | 'product' | 'partner' | 'licenseStart' | 'licenseEnd'
 *     | 'status' | 'salesOwner' | 'techOwner' | 'inspection' | 'note'
 */
import { gateway } from '../gateway'
import type { LicenseContract, LicenseContractQuery } from '../shared/model/types'
import { defaultMock } from './fake/default'
import { USER_ID } from './fake/seed/ids'

export const DEFAULT_CONTRACT_QUERY: LicenseContractQuery = { sort: 'licenseEnd', order: 'asc' }
export const STATUS_TEXT = { not_issued: '미발급', issued_new: '발급(신규)', issued_renewal: '발급(갱신)', ended: '종료' } as const

/** 모든 계약(admin으로 200건씩 끝까지 읽는다). */
export async function allContracts(query: LicenseContractQuery = DEFAULT_CONTRACT_QUERY): Promise<LicenseContract[]> {
  await defaultMock.signInAs(USER_ID.root)
  const found: LicenseContract[] = []
  for (let offset = 0; ; offset += 200) {
    const page = await gateway.licenseContracts.list(query, offset, 200)
    found.push(...page.items)
    if (found.length >= page.total || page.items.length === 0) return found
  }
}

export const firstWithStatus = (list: readonly LicenseContract[], status: LicenseContract['status']): LicenseContract => {
  const found = list.find((c) => c.status === status)
  if (!found) throw new Error(`상태 ${status} 계약이 시드에 없다`)
  return found
}

export const isIssued = (c: Pick<LicenseContract, 'status'>) => c.status === 'issued_new' || c.status === 'issued_renewal'
export const dotted = (iso: string) => iso.replaceAll('-', '.')
export const nextDay = (iso: string) => {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + 1)
  return d.toISOString().slice(0, 10)
}
