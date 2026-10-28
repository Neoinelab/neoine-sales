/** 분기 집합: 여러 분기를 고르는 화면(Dashboard 토글, Deal 목록 Quarter)이 함께 쓰는 URL 읽기·쓰기와 정규화. 없음 = 넷 다 = 전체. */

import { monthsOfQuarter } from './month'
import type { Quarter } from './period'

export const QUARTERS: readonly Quarter[] = [1, 2, 3, 4]

const QUARTER_ITEM = /^[1-4]$/

const ascending = (quarters: Iterable<Quarter>): Quarter[] => QUARTERS.filter((q) => new Set(quarters).has(q))

/** URL 분기 값('1,3') → 오름차순·중복 제거한 분기. 형식이 틀린 항목은 버린다. 넷 다여도 그대로 돌려준다(화면 표시용). */
export function parseQuarterParam(raw: string | null): Quarter[] {
  if (!raw) return []
  const found = raw
    .split(',')
    .map((item) => item.trim())
    .filter((item) => QUARTER_ITEM.test(item))
    .map((item) => Number(item) as Quarter)
  return ascending(found)
}

/** 분기 목록 → URL 값('1,3'). 비면 ''. */
export function quarterParam(quarters: Iterable<Quarter>): string {
  return ascending(quarters).join(',')
}

/** 한 분기를 켜거나 끈 뒤의 목록(오름차순). 받은 목록은 바꾸지 않는다. */
export function toggleQuarter(quarters: readonly Quarter[], quarter: Quarter, on: boolean): Quarter[] {
  return ascending(on ? [...quarters, quarter] : quarters.filter((q) => q !== quarter))
}

/** 조회·Drill-down용 정규화: 없음이나 넷 다면 [] (= 조건 없음). */
export function effectiveQuarters(quarters: readonly Quarter[]): Quarter[] {
  const list = ascending(quarters)
  return list.length === QUARTERS.length ? [] : list
}

/** 요약 문구: 조건이 없으면 '전체', 아니면 'Q1, Q3'. */
export function quarterSummary(quarters: readonly Quarter[]): string {
  const list = effectiveQuarters(quarters)
  return list.length === 0 ? '전체' : list.map((q) => `Q${q}`).join(', ')
}

/** 월 선택지: 조건이 없으면 12개월, 아니면 고른 분기들의 월 합집합(오름차순). */
export function monthsOfQuarters(quarters: readonly Quarter[]): readonly number[] {
  const list = effectiveQuarters(quarters)
  return (list.length === 0 ? QUARTERS : list).flatMap((q) => monthsOfQuarter(q))
}
