/** 서버 id의 형식: 1 이상 2^53-1 이하의 10진 정수(JSON 정수). */
const ID_TEXT = /^[1-9][0-9]*$/

/**
 * URL·DOM 같은 문자열 값을 id(number)로 바꾼다. 서버가 쓰는 범위(1 이상 안전 정수)가 아니면 undefined.
 * 빈 값·0·음수·부호·소수·지수·앞 0·공백·UUID·2^53 이상은 모두 거부한다.
 */
export function parseId(value: string | null | undefined): number | undefined {
  if (value == null || !ID_TEXT.test(value)) return undefined
  const id = Number(value)
  return Number.isSafeInteger(id) ? id : undefined
}
