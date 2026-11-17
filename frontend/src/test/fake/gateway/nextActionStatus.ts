/** Next Action 상태 규칙(서버 `NextActionStatus`와 같은 라벨·필터 확장). 테스트용 Fake 전용. */

import type { NextActionStatus, NextActionStatusFilter } from '../../../shared/model/types'
import { validation } from '../errors'
import { trimmedBody } from './commentRules'

export const STATUS_LABEL: Record<NextActionStatus, string> = {
  open: 'Open',
  done: '종료(수행)',
  notDone: '종료(미수행)',
}

/** `closed`는 종료(수행)·종료(미수행) 둘 다다. */
export function statusesOf(filter: NextActionStatusFilter): readonly NextActionStatus[] {
  return filter === 'closed' ? ['done', 'notDone'] : [filter]
}

export const NO_NEXT_ACTION = 'Next Action이 없는 Action은 상태를 바꿀 수 없습니다.'
export const STATUS_FORBIDDEN = '본인 Action 또는 admin만 Next Action 상태를 바꿀 수 있습니다.'
export const ACTION_OR_NEXT_REQUIRED = '진행사항 또는 Next Action을 입력하세요.'
export const DUE_WITHOUT_NEXT = 'Next Action 없이 Due Date를 입력할 수 없습니다.'
export const PREVIOUS_NEXT_ACTION_CHANGED = '이전 Next Action이 바뀌었습니다. 창을 닫고 다시 열어 주세요.'
export const OPEN_WITH_COMMENT = 'Open으로 되돌릴 때는 Comment를 남길 수 없습니다.'

/**
 * 상태 변경 Comment 검사(서버 CM-R15, NA-R7의 5단계 앞부분): NUL 거절 -> Open으로 되돌리며 Comment 거절.
 * 통과하면 앞뒤 공백을 지운 Comment(공백뿐이면 빈 문자열)를 돌려준다. 서버와 같은 문구의 422 `invalid-value`다.
 */
export function checkStatusComment(status: NextActionStatus, comment: string): string {
  const note = trimmedBody(comment)
  if (status === 'open' && note !== '') throw validation(OPEN_WITH_COMMENT)
  return note
}
