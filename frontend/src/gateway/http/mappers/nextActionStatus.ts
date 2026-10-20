import type { Schemas } from '../../../shared/api/client'
import type { NextActionStatus, NextActionStatusFilter } from '../../../shared/model/types'

/** 서버 `not_done` ↔ 화면 `notDone`. */
export function toNextActionStatus(wire: Schemas['NextActionStatus']): NextActionStatus {
  return wire === 'not_done' ? 'notDone' : wire
}

/** 화면 필터 → 서버 쿼리 값. */
export function toNextActionStatusParam(filter: NextActionStatusFilter): Schemas['NextActionStatusFilter'] {
  return filter === 'notDone' ? 'not_done' : filter
}
