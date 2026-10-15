import type { ActionsGateway } from '../../gateway/types'
import { canEditAction } from '../../shared/model/permissions'
import { compareIso, datePart } from '../../shared/model/dates'
import type { ActionInput, ActionQuery, ActionUpdateInput } from '../../shared/model/types'
import { forbidden, notFound, validation } from '../errors'
import { takeId, type ActionRecord } from '../store'
import { read, requireUser, requireWrite, write, type MockContext } from './context'
import { commitDealChange, planDealChange, type ChangeOutcome } from './dealChange'
import { logHistory } from './historyLog'
import { actionView, findDeal } from './views'

const DATE = /^\d{4}-\d{2}-\d{2}$/

/** 진행사항·Next Action·Due Date 필수(위에서부터 첫 오류). */
function validateFields(input: ActionUpdateInput): void {
  if (input.progress.trim() === '') throw validation('진행사항을 입력하세요.')
  if (input.nextAction.trim() === '') throw validation('Next Action을 입력하세요.')
  if (!DATE.test(input.dueDate)) throw validation('Due Date를 입력하세요.')
}

function summary(a: Pick<ActionRecord, 'type' | 'progress' | 'nextAction' | 'dueDate'>): string {
  return `${a.type} · ${a.progress} / Next Action: ${a.nextAction} (Due ${a.dueDate})`
}

function findAction(ctx: MockContext, id: string): ActionRecord {
  const found = ctx.store.data.actions.find((a) => a.id === id)
  if (!found) throw notFound('Action을 찾을 수 없습니다.')
  return found
}

function matches(a: ActionRecord, q: ActionQuery): boolean {
  if (q.type && a.type !== q.type) return false
  if (q.actorId && a.actorId !== q.actorId) return false
  if (q.keyword) {
    const needle = q.keyword.trim().toLowerCase()
    if (![a.progress, a.nextAction, a.memo].some((t) => t.toLowerCase().includes(needle))) return false
  }
  const acted = datePart(a.actedAt)
  if (q.actedFrom && acted < q.actedFrom) return false
  if (q.actedTo && acted > q.actedTo) return false
  if (q.dueFrom && a.dueDate < q.dueFrom) return false
  if (q.dueTo && a.dueDate > q.dueTo) return false
  return true
}

function sorted(rows: ActionRecord[], sort: ActionQuery['sort']): ActionRecord[] {
  const byActedDesc = (a: ActionRecord, b: ActionRecord) => compareIso(b.actedAt, a.actedAt) || b.id.localeCompare(a.id)
  if (sort === 'actedAsc') return rows.sort((a, b) => byActedDesc(b, a))
  if (sort === 'dueAsc') return rows.sort((a, b) => a.dueDate.localeCompare(b.dueDate) || byActedDesc(a, b))
  return rows.sort(byActedDesc)
}

export function createActionsGateway(ctx: MockContext): ActionsGateway {
  return {
    list: (dealCode, query) =>
      read(ctx, () => {
        requireUser(ctx)
        findDeal(ctx.store.data, dealCode)
        const rows = ctx.store.data.actions.filter((a) => a.dealCode === dealCode && matches(a, query))
        return sorted(rows, query.sort).map((a) => actionView(ctx.store.data, a))
      }),
    create: (dealCode, input: ActionInput) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        const deal = findDeal(data, dealCode)
        validateFields(input)
        let outcome: ChangeOutcome | null = null
        if (input.statusChange) outcome = planDealChange(ctx, deal, input.statusChange)
        if (outcome) commitDealChange(ctx, deal, outcome, user.id)
        const record: ActionRecord = {
          id: takeId(data.counters, 'act'),
          dealCode,
          actedAt: ctx.clock.now(),
          actorId: user.id,
          type: input.type,
          progress: input.progress.trim(),
          nextAction: input.nextAction.trim(),
          dueDate: input.dueDate,
          memo: input.memo,
          // 등록 시점(상태 변경이 있으면 적용 후) 값을 저장한다.
          statusKey: deal.statusKey,
          forecastKey: deal.forecastKey,
        }
        data.actions.push(record)
        logHistory(ctx, dealCode, user.id, 'action', 'Action', '', `등록: ${summary(record)}`)
        return actionView(data, record)
      }),
    update: (actionId, input: ActionUpdateInput) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        if (!canEditAction(user.role)) throw forbidden()
        const record = findAction(ctx, actionId)
        validateFields(input)
        const before = summary(record)
        Object.assign(record, {
          type: input.type,
          progress: input.progress.trim(),
          nextAction: input.nextAction.trim(),
          dueDate: input.dueDate,
          memo: input.memo,
        })
        logHistory(ctx, record.dealCode, user.id, 'action', 'Action', before, `수정: ${summary(record)}`)
        return actionView(ctx.store.data, record)
      }),
    remove: (actionId) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        if (!canEditAction(user.role)) throw forbidden()
        const record = findAction(ctx, actionId)
        const { actions } = ctx.store.data
        actions.splice(actions.indexOf(record), 1)
        logHistory(ctx, record.dealCode, user.id, 'action', 'Action', summary(record), '삭제')
      }),
  }
}
