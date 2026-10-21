import type { Vendor } from './types'

/**
 * 조회 조건의 Vendor·Solution을 화면 표시와 맞춘다(표시 = 조회 조건).
 * 목록(`vendors`)을 아직 모르면(로딩·오류) 판단하지 않고 그대로 돌려준다.
 * 목록에 없는 vendor/solution id와, 유효한 Vendor 소속이 아닌 Solution은 제외한다.
 */
export function effectiveVendorFilter(
  vendors: Vendor[] | undefined,
  vendorId: number | undefined,
  solutionId?: number,
): { vendorId?: number; solutionId?: number } {
  if (!vendors) return { vendorId, solutionId }
  const vendor = vendorId ? vendors.find((v) => v.id === vendorId) : undefined
  const pool = vendor ? vendor.solutions : vendors.flatMap((v) => v.solutions)
  const solution = solutionId && pool.some((s) => s.id === solutionId) ? solutionId : undefined
  return { vendorId: vendor?.id, solutionId: solution }
}
