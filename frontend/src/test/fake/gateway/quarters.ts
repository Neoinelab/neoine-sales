import { validation } from '../errors'

/**
 * 서버(`normalize_quarters`)와 같은 규칙을 Fake가 독립적으로 구현한다(운영 코드 `quarterSet.ts`를 가져오지 않는다).
 * 없음·빈 목록·넷 다 = 조건 없음(undefined). 1~4 밖 값이나 4개를 넘는 목록은 422.
 */
export function normalizedQuarters(raw: readonly number[] | undefined): readonly number[] | undefined {
  if (raw === undefined || raw.length === 0) return undefined
  if (raw.length > 4 || raw.some((q) => !Number.isInteger(q) || q < 1 || q > 4)) throw validation('분기는 1~4 중에서 선택하세요.')
  const unique = [...new Set(raw)].sort((a, b) => a - b)
  return unique.length === 4 ? undefined : unique
}

/** 월(1~12)이 속한 분기. */
export const quarterOfMonth = (month: number): number => Math.floor((month - 1) / 3) + 1
