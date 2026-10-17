/** mock 시계. 실제 시각 또는 테스트용 고정 시각을 돌려준다. 모든 mock 시각은 이 시계에서 나온다. */

import { datePart, formatWithOffset, offsetMinutes } from '../../shared/model/dates'

export interface MockClock {
  /** 오프셋 포함 ISO 문자열. */
  now(): string
  /** 'YYYY-MM-DD'(now의 현지 달력 날짜). */
  today(): string
  /** ISO 문자열로 고정하거나 null이면 실제 시각으로 돌아간다. */
  setNow(iso: string | null): void
  /** 시계를 ms만큼 앞으로 보낸다(실제 시각 모드였다면 그 시점에서 고정된다). */
  advance(ms: number): void
  isFixed(): boolean
}

export function createClock(fixed: string | null = null): MockClock {
  let current = fixed
  const realNow = (): string => formatWithOffset(Date.now(), -new Date().getTimezoneOffset())
  const now = (): string => current ?? realNow()
  return {
    now,
    today: () => datePart(now()),
    setNow(iso) {
      current = iso
    },
    advance(ms) {
      const base = now()
      current = formatWithOffset(Date.parse(base) + ms, offsetMinutes(base))
    },
    isFixed: () => current !== null,
  }
}
