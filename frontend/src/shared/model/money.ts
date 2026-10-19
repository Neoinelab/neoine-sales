/** 금액 표기·검증 순수 함수. 저장·API는 원 단위, 화면은 천원 단위(값에 단위 글자 없음, 단위는 항목 이름에). */

/** 금액 항목 이름(열 머리글·dt·폼 라벨·접근성 이름·History 대상). 서버 history.py의 AMOUNT_TARGET과 같다. */
export const AMOUNT_LABEL = '금액(단위:천원)'
/** 매출 확정 팝업의 금액 라벨. */
export const REVENUE_AMOUNT_LABEL = '매출금액(단위:천원, 실제 값)'
/** 입력 가능한 최대 천원 값 = floor((2^53−1) / 1000). */
export const THOUSAND_WON_MAX = 9_007_199_254_740
export const AMOUNT_INPUT_MESSAGE = '매출금액은 천원 단위로 1 이상의 정수를 입력하세요.'
export const AMOUNT_TOO_LARGE_MESSAGE = '매출금액은 천원 단위로 9,007,199,254,740 이하로 입력하세요.'

/** 매출금액 유효성(원 기준): 1 이상의 안전 정수. */
export function isValidAmount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1
}

/** 원 → 천원(half-up). 부동소수 오차를 피하려고 나머지로 계산한다. */
export function toThousandWon(won: number): number {
  const rest = won % 1000
  const base = (won - rest) / 1000
  return rest >= 500 ? base + 1 : base
}

/** 원 → 천원 콤마 숫자(단위 글자 없음). 표시와 편집 시작값에 모두 쓴다. */
export function formatThousandWon(won: number): string {
  return toThousandWon(won).toLocaleString('en-US')
}

function thousandsOf(text: string): number | null {
  const cleaned = text.trim().replaceAll(',', '')
  if (!/^\d+$/.test(cleaned)) return null
  const value = Number(cleaned)
  return Number.isSafeInteger(value) ? value : null
}

/** 천원 입력 문자열 → 원 금액. 빈 값·0·소수·음수·문자·최대 초과면 null. */
export function parseAmountInput(text: string): number | null {
  const thousands = thousandsOf(text)
  if (thousands === null || thousands < 1 || thousands > THOUSAND_WON_MAX) return null
  return thousands * 1000
}

/** 검증 문구: 유효하면 null. */
export function amountInputError(text: string): string | null {
  if (parseAmountInput(text) !== null) return null
  const cleaned = text.trim().replaceAll(',', '')
  if (/^\d+$/.test(cleaned) && cleaned.replace(/^0+/, '').length > 0) {
    const thousands = Number(cleaned)
    if (!Number.isSafeInteger(thousands) || thousands > THOUSAND_WON_MAX) return AMOUNT_TOO_LARGE_MESSAGE
  }
  return AMOUNT_INPUT_MESSAGE
}

/** 입력값(원)이 원래 값(원)과 화면 표기상 같은가. 같으면 호출처는 원래 원 값을 유지한다. */
export function isSameShownAmount(inputWon: number, originalWon: number): boolean {
  return toThousandWon(inputWon) === toThousandWon(originalWon)
}

/** 입력 중 자동 콤마: 숫자 외 문자는 버리고 앞자리 0을 지우며, 커서는 왼쪽 숫자 개수를 유지한다. */
export function formatAmountInput(raw: string, caret: number): { text: string; caret: number } {
  const digitsBefore = raw.slice(0, caret).replace(/\D/g, '').length
  let digits = raw.replace(/\D/g, '')
  const stripped = digits.replace(/^0+(?=\d)/, '')
  const removed = digits.length - stripped.length
  digits = stripped
  const keep = Math.max(0, Math.min(digitsBefore - removed, digits.length))
  const text = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  // 커서 왼쪽 숫자 keep개 뒤의 위치를 text에서 찾는다.
  let seen = 0
  let pos = 0
  while (pos < text.length && seen < keep) {
    if (text[pos] !== ',') seen += 1
    pos += 1
  }
  return { text, caret: pos }
}
