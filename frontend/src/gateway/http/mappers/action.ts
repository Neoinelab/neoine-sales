import type { Schemas } from '../../../shared/api/client'
import type { ActionInput, ActionUpdateInput, DealAction } from '../../../shared/model/types'
import { toUserRef } from './user'

/** 서버 Action → 화면 DealAction. 텍스트는 가공하거나 자르지 않는다. */
export function toDealAction(row: Schemas['DealActionResponse']): DealAction {
  return {
    id: row.id,
    dealCode: row.deal_code,
    actedAt: row.acted_at,
    actor: toUserRef(row.actor),
    type: row.action_type.name,
    typeId: row.action_type.id,
    progress: row.action,
    nextAction: row.next_action,
    dueDate: row.due_date,
    memo: row.memo,
    statusKey: row.status_key,
    forecastKey: row.forecast_key,
  }
}

/** 텍스트는 그대로(trim은 서버 몫), 빈 Due Date만 null로 보내 서버가 자기 문구로 답하게 한다. */
export function toActionUpdateBody(input: ActionUpdateInput): Schemas['DealActionUpdateRequest'] {
  return {
    action_type: { ...input.type },
    action: input.progress,
    next_action: input.nextAction,
    due_date: input.dueDate === '' ? null : input.dueDate,
    memo: input.memo,
  }
}

function toStatusChange(change: NonNullable<ActionInput['statusChange']>): Schemas['ActionStatusChangeRequest'] {
  const field = change.change.field === 'statusKey' ? 'status_key' : 'forecast_key'
  const body: Schemas['ActionStatusChangeRequest'] = { change: { field, value: change.change.value } }
  const r = change.resolution
  if (r) {
    const resolution: Schemas['ResolutionRequest'] = {}
    if (r.revenueAmount !== undefined) resolution.revenue_amount = r.revenueAmount
    if (r.revenueDate !== undefined) resolution.revenue_date = r.revenueDate
    if (r.statusKey !== undefined) resolution.status_key = r.statusKey
    if (r.forecastKey !== undefined) resolution.forecast_key = r.forecastKey
    body.resolution = resolution
  }
  return body
}

/** 수행일시·담당자는 서버가 정하므로 보내지 않는다. */
export function toActionCreateBody(input: ActionInput): Schemas['DealActionCreateRequest'] {
  const body: Schemas['DealActionCreateRequest'] = toActionUpdateBody(input)
  if (input.statusChange) body.status_change = toStatusChange(input.statusChange)
  return body
}
