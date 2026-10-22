/**
 * 테스트 전용 샘플 Vendor(등록 목록). 앱 기본 시드에는 없고 `buildSampleSeed`만 얹는다.
 * id는 정렬 순서(소문자 이름 코드 포인트 순)대로 1부터 정수로 정해진다. Solution은 Vendor 관리
 * 대상이 아니라 Deal의 자유 텍스트이므로 여기에 없다.
 * - Splunk: 쓰는 Deal이 없다 → 삭제 가능(확인 문구 테스트용)
 * - Veeam: 쓰는 Deal이 없다 → 삭제 가능
 */

export interface SeedVendor {
  id: number
  name: string
}

const NAMES: readonly string[] = [
  'CrowdStrike',
  'CyberArk',
  'Okta',
  'Palo Alto',
  'SentinelOne',
  'Silverfort',
  'Splunk',
  'Tenable',
  'Veeam',
  'Zscaler',
]

export const SEED_VENDORS: readonly SeedVendor[] = NAMES.map((name, index) => ({ id: index + 1, name }))

export function seedVendorId(name: string): number {
  const found = SEED_VENDORS.find((v) => v.name === name)
  if (!found) throw new Error(`시드 Vendor 없음: ${name}`)
  return found.id
}
