import type { Vendor } from './types'

/**
 * 조회 조건의 Vendor를 화면 표시와 맞춘다(표시 = 조회 조건).
 * 목록(`vendors`)을 아직 모르면(로딩·오류) 판단하지 않고 그대로 돌려준다. 목록에 없는 vendor id는 제외한다.
 */
export function effectiveVendorFilter(vendors: Vendor[] | undefined, vendorId: number | undefined): { vendorId?: number } {
  if (!vendors) return { vendorId }
  const vendor = vendorId ? vendors.find((v) => v.id === vendorId) : undefined
  return { vendorId: vendor?.id }
}
