/** 금액 표기·검증 순수 함수. 저장·API·화면 모두 원 단위(값에 단위 글자 없음, 단위는 항목 이름에). */

/** 금액 항목 이름(열 머리글·dt·폼 라벨·접근성 이름·History 대상). 서버 history.py의 AMOUNT_TARGET과 같다. */
export const AMOUNT_LABEL = '금액(단위:원)'
/** 매출 확정 팝업의 금액 라벨. */
export const REVENUE_AMOUNT_LABEL = '매출금액(단위:원, 실제 값)'
/** 입력 가능한 최대 원 값 = 2^53−1(서버 RevenueAmount 상한). */
export const WON_MAX = Number.MAX_SAFE_INTEGER
export const AMOUNT_INPUT_MESSAGE = '매출금액은 1원 이상의 정수를 입력하세요.'
export const AMOUNT_TOO_LARGE_MESSAGE = '매출금액은 9,007,199,254,740,991원 이하로 입력하세요.'

/** 매출금액 유효성(원 기준): 1 이상의 안전 정수. */
export function isValidAmount(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 1
}

/** 원 콤마 숫자(단위 글자 없음, 반올림 없음). 표시와 편집 시작값에 모두 쓴다. */
export function formatWon(won: number | null): string {
  return won === null ? '-' : won.toLocaleString('en-US')
}

function shortened(value: number, unit: number, suffix: string): string {
  return `${(value / unit).toLocaleString('en-US', { maximumFractionDigits: 1 })}${suffix}`
}

/** 차트 금액 축 눈금: 1억 이상 `억`, 1만 이상 `만`, 그 미만은 콤마 숫자. 단위는 반올림한 값으로 정한다. */
export function formatWonAxis(value: number): string {
  if (value === 0) return '0'
  const abs = Math.abs(value)
  if (abs >= 1e8) return shortened(value, 1e8, '억')
  if (abs >= 1e4) {
    // 만 단위를 소수 1자리로 반올림했을 때 10,000만이 되면 1억으로 올린다.
    if (Math.round((abs / 1e4) * 10) / 10 >= 1e4) return shortened(value, 1e8, '억')
    return shortened(value, 1e4, '만')
  }
  return formatWon(value)
}

function wholeOf(text: string): number | null {
  const cleaned = text.trim().replaceAll(',', '')
  if (!/^\d+$/.test(cleaned)) return null
  const value = Number(cleaned)
  return Number.isSafeInteger(value) ? value : null
}

/** 원 입력 문자열 → 원 금액. 빈 값·0·소수·음수·문자·최대 초과면 null. */
export function parseAmountInput(text: string): number | null {
  const won = wholeOf(text)
  if (won === null || won < 1 || won > WON_MAX) return null
  return won
}

/** 검증 문구: 유효하면 null. */
export function amountInputError(text: string): string | null {
  if (parseAmountInput(text) !== null) return null
  const cleaned = text.trim().replaceAll(',', '')
  if (/^\d+$/.test(cleaned) && cleaned.replace(/^0+/, '').length > 0) {
    const won = Number(cleaned)
    if (!Number.isSafeInteger(won) || won > WON_MAX) return AMOUNT_TOO_LARGE_MESSAGE
  }
  return AMOUNT_INPUT_MESSAGE
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
