/** 한국어 조사 보조(알림 문구용). 한글은 받침으로, 영문은 대략적인 발음 규칙(l m n k p b g c x로 끝나거나 모음 바로 뒤의 t로 끝나면 받침, 예: Commit은 받침·Best는 없음)으로 판단한다. */

function hasBatchim(text: string): boolean {
  const last = text.trimEnd().slice(-1)
  if (last === '') return false
  const code = last.charCodeAt(0)
  if (code >= 0xac00 && code <= 0xd7a3) return (code - 0xac00) % 28 !== 0
  if (/[0-9]/.test(last)) return '013678'.includes(last)
  if (/t/i.test(last)) return /[aeiou]t$/i.test(text.trimEnd())
  return /[lmnkpbgcx]/i.test(last)
}

/** '로' / '으로'. ㄹ 받침은 '로'. */
export function withRo(text: string): string {
  const last = text.trimEnd().slice(-1)
  const code = last.charCodeAt(0)
  const isRieul = code >= 0xac00 && code <= 0xd7a3 && (code - 0xac00) % 28 === 8
  return hasBatchim(text) && !isRieul ? `${text}으로` : `${text}로`
}

/** '가' / '이'. */
export function withGa(text: string): string {
  return hasBatchim(text) ? `${text}이` : `${text}가`
}

/** '와' / '과'. */
export function withWa(text: string): string {
  return hasBatchim(text) ? `${text}과` : `${text}와`
}
