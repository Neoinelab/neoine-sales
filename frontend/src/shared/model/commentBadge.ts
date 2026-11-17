/** 읽지 않은 Comment 수 배지 글자. 0 이하는 배지 없음(null), 100건 이상은 "99+". */
export function badgeText(count: number): string | null {
  if (count <= 0) return null
  return count > 99 ? '99+' : String(count)
}
