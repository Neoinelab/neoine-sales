/**
 * 테스트 전용 샘플 Vendor·Solution(등록 목록). 앱 기본 시드에는 없고 `buildSampleSeed`만 얹는다.
 * id는 정렬 순서(소문자 이름 코드 포인트 순)대로 Vendor는 1부터, Solution은 1부터 정수로 정해진다.
 * - Splunk: 쓰는 Deal이 없고 Solution이 2개(SIEM, SOAR) → 삭제 확인 문구(소속 Solution N개) 테스트용
 * - Veeam: 쓰는 Deal도 Solution도 없음 → 둘째 문장이 없는 삭제 확인 문구 테스트용
 */

export interface SeedSolution {
  id: number
  name: string
}

export interface SeedVendor {
  id: number
  name: string
  solutions: SeedSolution[]
}

const RAW: readonly { name: string; solutions: readonly string[] }[] = [
  { name: 'CrowdStrike', solutions: ['EDR'] },
  { name: 'CyberArk', solutions: ['PAM'] },
  { name: 'Okta', solutions: ['SSO'] },
  { name: 'Palo Alto', solutions: ['NGFW'] },
  { name: 'SentinelOne', solutions: ['EDR'] },
  { name: 'Silverfort', solutions: ['ITDR', 'MFA'] },
  { name: 'Splunk', solutions: ['SIEM', 'SOAR'] },
  { name: 'Tenable', solutions: ['VM'] },
  { name: 'Veeam', solutions: [] },
  { name: 'Zscaler', solutions: ['ZTNA'] },
]

let solutionNo = 0
export const SEED_VENDORS: readonly SeedVendor[] = RAW.map((vendor, index) => ({
  id: index + 1,
  name: vendor.name,
  solutions: vendor.solutions.map((name) => {
    solutionNo += 1
    return { id: solutionNo, name }
  }),
}))

export const SEED_SOLUTION_COUNT = solutionNo

export function seedVendorId(name: string): number {
  const found = SEED_VENDORS.find((v) => v.name === name)
  if (!found) throw new Error(`시드 Vendor 없음: ${name}`)
  return found.id
}

export function seedSolutionId(vendor: string, solution: string): number {
  const found = SEED_VENDORS.find((v) => v.name === vendor)?.solutions.find((s) => s.name === solution)
  if (!found) throw new Error(`시드 Solution 없음: ${vendor} / ${solution}`)
  return found.id
}
