import type { ActionsGateway } from '../../gateway/types'
import { canEditAction } from '../../shared/model/permissions'
import { compareIso } from '../../shared/model/dates'
import type { ActionInput, ActionQuery, ActionUpdateInput } from '../../shared/model/types'
import { forbidden, notFound, validation } from '../errors'
import { takeId, type ActionRecord } from '../store'
import { read, requireUser, requireWrite, viewerOf, write, type MockContext } from './context'
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

type Content = Pick<ActionRecord, 'type' | 'progress' | 'nextAction' | 'dueDate' | 'memo'>

function summary(a: Content): string {
  const base = `${a.type} · ${a.progress} / Next Action: ${a.nextAction} (Due ${a.dueDate})`
  return a.memo === '' ? base : `${base} / Memo: ${a.memo}`
}

const same = (a: Content, b: Content): boolean =>
  a.type === b.type && a.progress === b.progress && a.nextAction === b.nextAction && a.dueDate === b.dueDate && a.memo === b.memo

const pad = (n: number): string => String(n).padStart(2, '0')

/** 인스턴트를 브라우저(로컬) 달력 날짜로 바꾼다. 문자열 날짜 부분은 오프셋에 따라 어긋날 수 있다. */
function localDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function validateRanges(q: ActionQuery): void {
  if (q.actedFrom && q.actedTo && q.actedFrom > q.actedTo) throw validation('수행일 범위의 시작은 끝보다 늦을 수 없습니다.')
  if (q.dueFrom && q.dueTo && q.dueFrom > q.dueTo) throw validation('Due Date 범위의 시작은 끝보다 늦을 수 없습니다.')
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
  const acted = localDate(a.actedAt)
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
        validateRanges(query)
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
          memo: input.memo.trim(),
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
        const user = requireWrite(ctx)
        const record = findAction(ctx, actionId)
        if (!canEditAction(viewerOf(user), record.actorId)) throw forbidden('본인 Action 또는 admin만 수정할 수 있습니다.')
        validateFields(input)
        const next: Content = {
          type: input.type,
          progress: input.progress.trim(),
          nextAction: input.nextAction.trim(),
          dueDate: input.dueDate,
          memo: input.memo.trim(),
        }
        if (same(record, next)) return actionView(ctx.store.data, record)
        const before = summary(record)
        Object.assign(record, next)
        logHistory(ctx, record.dealCode, user.id, 'action', 'Action', before, `수정: ${summary(record)}`)
        return actionView(ctx.store.data, record)
      }),
    remove: (actionId) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const record = findAction(ctx, actionId)
        if (!canEditAction(viewerOf(user), record.actorId)) throw forbidden('본인 Action 또는 admin만 삭제할 수 있습니다.')
        const { actions } = ctx.store.data
        actions.splice(actions.indexOf(record), 1)
        logHistory(ctx, record.dealCode, user.id, 'action', 'Action', summary(record), '삭제')
      }),
  }
}
