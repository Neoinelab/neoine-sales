/** 금액 표기·검증 순수 함수(A-0 계약, 구현은 A-1). KRW 정수 기준, PRD 11.1 "M = 백만, B = 10억". */

/**
 * 짧은 표기.
 * - >= 1,000,000,000: B, 소수 둘째 자리까지 반올림 후 뒤 0 제거. 1,870,000,000 → '1.87B', 1,000,000,000 → '1B'
 * - >= 1,000,000: M, 같은 방식. 180,000,000 → '180M', 1,234,567 → '1.23M', 999,999,999 → '1,000M'(원값 기준 M 구간)
 * - < 1,000,000: 콤마 숫자 + '원'. 999,999 → '999,999원', 0 → '0원'
 */
export function formatKrwShort(amount: number): string {
  if (amount >= 1_000_000_000) return `${group(amount / 1_000_000_000)}B`
  if (amount >= 1_000_000) return `${group(amount / 1_000_000)}M`
  return `${amount.toLocaleString('en-US')}원`
}

/** 소수 둘째 자리까지 반올림, 뒤 0 제거, 천 단위 콤마. */
function group(value: number): string {
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 })
}

/** 전체 표기(hover title 등): 콤마 숫자 + '원'. 1870000000 → '1,870,000,000원' */
export function formatKrwFull(amount: number): string {
  return `${amount.toLocaleString('en-US')}원`
}

/** 매출금액 유효성: 1 이상의 안전 정수. */
export function isValidAmount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1
}

/**
 * 입력 문자열 → 금액. 콤마·앞뒤 공백 허용('1,870,000,000'), 소수점·음수·문자·빈 값은 null,
 * 0도 null(1원 미만 불가).
 */
export function parseAmount(text: string): number | null {
  const cleaned = text.trim().replaceAll(',', '')
  if (!/^\d+$/.test(cleaned)) return null
  const value = Number(cleaned)
  return isValidAmount(value) ? value : null
}
