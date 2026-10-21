/** 월(1~12)의 URL 형식: 앞 0·부호·공백 없는 10진 문자열. */
const MONTH_TEXT = /^([1-9]|1[0-2])$/

/** URL 문자열 값을 월(1~12)로 바꾼다. 형식에 맞지 않으면 undefined. */
export function parseMonth(raw: string | null | undefined): number | undefined {
  return raw != null && MONTH_TEXT.test(raw) ? Number(raw) : undefined
}
