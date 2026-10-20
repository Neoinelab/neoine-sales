/** Action 등록의 순차 Status·Forecast 변경(최대 2개). 서버 `finalize_sequence`와 같은 판정 순서·충돌 규칙을 따른다. */

import type { Deal, StatusChangeRequest } from '../../../shared/model/types'
import { SYNC_CONFLICT_MESSAGE, overridesRequested, type SyncChange } from '../../../shared/model/sync'
import type { MockContext } from './context'
import { validation } from '../errors'
import { assertCodeExists, planDealChange, type ChangeOutcome } from './dealChange'

const MAX_STEPS = 2
const INVALID_FORM = '요청 형식이 올바르지 않습니다'

/** 개수·field 중복 검사. 서버는 요청 검증 단계(Deal 조회 전)에서 422로 거절한다. */
export function assertSequenceShape(steps: StatusChangeRequest[]): void {
  const fields = steps.map((s) => s.change.field)
  if (steps.length > MAX_STEPS || new Set(fields).size !== fields.length) throw validation(INVALID_FORM)
}

/** 모든 변경을 앞에서부터 판정한다(아무것도 바꾸지 않는다). 하나라도 틀리면 ApiError(422). */
export function planSequence(ctx: MockContext, deal: Deal, steps: StatusChangeRequest[]): ChangeOutcome[] {
  assertSequenceShape(steps)
  for (const step of steps) assertCodeExists(ctx, step)
  const outcomes: ChangeOutcome[] = []
  let state: Deal = deal
  for (const step of steps) {
    const outcome = planDealChange(ctx, state, step)
    outcomes.push(outcome)
    state = { ...state, ...outcome.patch }
  }
  const [first, second] = steps
  const [firstOutcome, secondOutcome] = outcomes
  if (first && second && firstOutcome && secondOutcome) {
    const change = first.change as SyncChange
    const afterFirst = { ...deal, ...firstOutcome.patch }
    const applied = { patch: secondOutcome.patch, revenue: null, coChanged: [], notice: null }
    if (overridesRequested(change, afterFirst, applied)) throw validation(SYNC_CONFLICT_MESSAGE)
  }
  return outcomes
}
