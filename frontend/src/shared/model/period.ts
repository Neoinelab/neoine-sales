/** 연/분기 분류와 사용자 표시명(A-0 계약). Forecast 요약·Deal 목록의 year/quarter 필터가 같은 함수를 쓴다. */

import type { UserRef } from './types'

export type Quarter = 1 | 2 | 3 | 4

/**
 * 'YYYY-MM-DD' → {year, quarter}. 1~3월 Q1, 4~6월 Q2, 7~9월 Q3, 10~12월 Q4.
 * 경계: '2026-12-31' → {2026,4}, '2027-01-01' → {2027,1}.
 */
export function periodOf(date: string): { year: number; quarter: Quarter } {
  const year = Number(date.slice(0, 4))
  const month = Number(date.slice(5, 7))
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) {
    throw new RangeError(`날짜 형식이 올바르지 않습니다: ${date}`)
  }
  return { year, quarter: (Math.ceil(month / 3) as Quarter) }
}

/** 날짜가 해당 연도(그리고 quarter가 있으면 분기)에 속하는지. */
export function inPeriod(date: string, year: number, quarter?: Quarter): boolean {
  const p = periodOf(date)
  return p.year === year && (quarter === undefined || p.quarter === quarter)
}

/** 퇴사자는 '이름(퇴사)', 아니면 이름. 모든 화면의 사용자 표시명. */
export function userLabel(user: Pick<UserRef, 'name' | 'status'>): string {
  return user.status === 'resigned' ? `${user.name}(퇴사)` : user.name
}
