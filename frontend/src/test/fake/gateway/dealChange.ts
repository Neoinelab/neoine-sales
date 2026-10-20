/** 단일 필드 변경(Status/Forecast/금액/Expected Close)의 계획·확정. deals.applyChange와 actions.create(statusChange)가 공유한다. */

import type { ApplyChangeRequest } from '../../../shared/model/types'
import { isValidAmount } from '../../../shared/model/money'
import { finalizePlan, planChange, type CoChange } from '../../../shared/model/sync'
import type { CodeSet, Deal } from '../../../shared/model/types'
import { clone, type MockContext } from './context'
import { validation } from '../errors'
import { logDealDiff } from './historyLog'

type ChangedFields = Partial<Pick<Deal, 'statusKey' | 'forecastKey' | 'revenueAmount' | 'revenueDate'>>

export interface ChangeOutcome {
  patch: ChangedFields
  coChanged: CoChange[]
  notice: string | null
}

export function codeSetOf(ctx: MockContext): CodeSet {
  const byOrder = (kind: 'status' | 'forecast') =>
    ctx.store.data.codes.filter((c) => c.kind === kind).sort((a, b) => a.order - b.order)
  return { statuses: byOrder('status'), forecasts: byOrder('forecast') }
}

/** Status·Forecast 변경의 코드가 존재하는지 확인한다(다른 판정보다 먼저). 틀리면 ApiError(422). */
export function assertCodeExists(ctx: MockContext, request: ApplyChangeRequest): void {
  const { change } = request
  if (change.field !== 'statusKey' && change.field !== 'forecastKey') return
  const codes = codeSetOf(ctx)
  const list = change.field === 'statusKey' ? codes.statuses : codes.forecasts
  if (!list.some((c) => c.key === change.value)) throw validation('존재하지 않는 코드입니다.')
}

/** 검증만 하고 아무것도 바꾸지 않는다. 틀리면 ApiError(422). */
export function planDealChange(ctx: MockContext, deal: Deal, request: ApplyChangeRequest): ChangeOutcome {
  const { change, resolution } = request
  if (change.field === 'revenueAmount') {
    if (!isValidAmount(change.value)) throw validation('매출금액은 1원 이상의 정수로 입력하세요.')
    return { patch: { revenueAmount: change.value }, coChanged: [], notice: null }
  }
  if (change.field === 'revenueDate') {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(change.value)) throw validation('Expected Close를 입력하세요.')
    return { patch: { revenueDate: change.value }, coChanged: [], notice: null }
  }

  assertCodeExists(ctx, request)
  const codes = codeSetOf(ctx)
  const plan = planChange(deal, change, codes)
  const result = finalizePlan(deal, plan, resolution, codes)
  if (!result.ok) throw validation(result.message)
  const { applied } = result
  const patch: ChangedFields = { ...applied.patch }
  if (applied.revenue) {
    patch.revenueAmount = applied.revenue.amount
    patch.revenueDate = applied.revenue.date
  }
  return { patch, coChanged: applied.coChanged, notice: applied.notice }
}

/** 계획을 적용하고 바뀐 필드를 History에 남긴다. 바뀐 것이 없으면 updatedAt도 그대로 둔다. */
export function commitDealChange(ctx: MockContext, deal: Deal, outcome: ChangeOutcome, byId: string): void {
  const before = clone(deal)
  Object.assign(deal, outcome.patch)
  if (deal.statusKey !== before.statusKey) deal.statusChangedAt = ctx.clock.now()
  const logged = logDealDiff(ctx, before, deal, byId, outcome.coChanged)
  if (logged > 0) deal.updatedAt = ctx.clock.now()
}
