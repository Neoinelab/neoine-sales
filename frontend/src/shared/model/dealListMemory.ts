/** Deals 목록 필터 키. 조건·정렬·페이지가 모두 URL에 있어 상세에 다녀와도 유지된다(DL-06). */
export const FILTER_KEYS = [
  'q',
  'owner',
  'vendor',
  'solution',
  'status',
  'forecast',
  'year',
  'quarter',
  'from',
  'to',
  'budget',
  'authority',
  'need',
  'timeline',
  'mine',
  'next_status',
] as const

/** 목록 조건으로 기억하는 쿼리 키: 필터 16개 + 정렬·페이지. */
export const REMEMBERED_LIST_KEYS: readonly string[] = [...FILTER_KEYS, 'sort', 'order', 'page']

const LIST_PATH = '/deals'

/** 저장 키. 사용자별로 분리한다. */
export function listMemoryKey(userId: string): string {
  return `deals.listSearch:${userId}`
}

/** 아는 키만 남긴 쿼리 문자열(앞의 '?' 없음). 키 순서는 입력 순서를 유지한다. 값은 검증하지 않는다. */
export function sanitizeListSearch(search: string | URLSearchParams): string {
  const source = typeof search === 'string' ? new URLSearchParams(search) : search
  const kept = new URLSearchParams()
  source.forEach((value, key) => {
    if (REMEMBERED_LIST_KEYS.includes(key)) kept.append(key, value)
  })
  return kept.toString()
}

/** sessionStorage에 기록한다. 거른 결과가 비면 항목을 지운다. 저장소 예외는 삼킨다(기억은 부가 기능). */
export function rememberListSearch(userId: string, search: URLSearchParams): void {
  const clean = sanitizeListSearch(search)
  try {
    if (clean === '') window.sessionStorage.removeItem(listMemoryKey(userId))
    else window.sessionStorage.setItem(listMemoryKey(userId), clean)
  } catch {
    // 저장소를 쓸 수 없으면 기억만 포기한다.
  }
}

/** 기억한 조건으로 만든 목록 경로. 사용자를 모르거나 저장이 없거나 읽기에 실패하면 '/deals'. */
export function rememberedListPath(userId: string | null | undefined): string {
  if (!userId) return LIST_PATH
  try {
    const stored = window.sessionStorage.getItem(listMemoryKey(userId))
    const clean = stored === null ? '' : sanitizeListSearch(stored)
    return clean === '' ? LIST_PATH : `${LIST_PATH}?${clean}`
  } catch {
    return LIST_PATH
  }
}
