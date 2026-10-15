import { mockControl } from '../gateway'
import { datePart } from '../shared/model/dates'

export interface Today {
  /** mock 시계의 지금(오프셋 포함 ISO). */
  now: string
  /** 'YYYY-MM-DD'. */
  today: string
  year: number
}

/**
 * mock 시계의 오늘. 화면은 `new Date()` 대신 이 훅을 써서 시드 날짜(시계 기준 상대값)와 같은 기준으로 계산한다.
 * 매 렌더마다 시계를 읽는다(구독하지 않는다).
 */
export function useToday(): Today {
  const now = mockControl.now()
  const today = datePart(now)
  return { now, today, year: Number(today.slice(0, 4)) }
}
