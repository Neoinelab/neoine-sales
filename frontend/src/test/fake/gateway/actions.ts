import type { ActionsGateway } from '../../../gateway/types'
import { canEditAction } from '../../../shared/model/permissions'
import { compareIso } from '../../../shared/model/dates'
import type {
  ActionInput,
  ActionQuery,
  ActionUpdateInput,
  NextActionStatus,
} from '../../../shared/model/types'
import { conflict, forbidden, notFound, validation } from '../errors'
import { takeId, type ActionRecord, type SeedData } from '../store'
import { read, requireUser, requireWrite, viewerOf, write, type MockContext } from './context'
import { assertSequenceShape, planSequence } from './actionChanges'
import { commitDealChange } from './dealChange'
import { commitActionType, planActionType } from './actionTypes'
import { logHistory } from './historyLog'
import { ACTION_OR_NEXT_REQUIRED, DUE_WITHOUT_NEXT, NO_NEXT_ACTION, STATUS_FORBIDDEN, STATUS_LABEL, statusesOf } from './nextActionStatus'
import { actionView, findDeal, userRef } from './views'

const DATE = /^\d{4}-\d{2}-\d{2}$/

type Content = Pick<ActionRecord, 'typeId' | 'progress' | 'nextAction' | 'dueDate' | 'memo'>

const blankToNull = (text: string): string | null => (text.trim() === '' ? null : text.trim())

/**
 * 서버 규칙: 진행사항·Next Action 중 하나 이상(둘 다 비면 422), Next Action이 있으면 Due Date 필수,
 * 없으면 Due Date 금지(위에서부터 첫 오류). 비운 값은 null로 저장한다.
 */
function normalize(input: ActionUpdateInput, typeId: number): Content {
  const progress = blankToNull(input.progress)
  const nextAction = blankToNull(input.nextAction)
  if (progress === null && nextAction === null) throw validation(ACTION_OR_NEXT_REQUIRED)
  if (nextAction !== null && !DATE.test(input.dueDate)) throw validation('Due Date를 입력하세요.')
  if (nextAction === null && input.dueDate !== '') throw validation(DUE_WITHOUT_NEXT)
  return { typeId, progress, nextAction, dueDate: nextAction === null ? null : input.dueDate, memo: input.memo.trim() }
}

/** History 문구의 유형 자리에는 그 시점의 유형 이름이 들어간다(이미 남은 문구는 이름이 바뀌어도 그대로). 빈 부분은 생략한다. */
function summary(ctx: MockContext, a: Content): string {
  const typeName = ctx.store.data.actionTypes.find((t) => t.id === a.typeId)?.name ?? a.typeId
  const progress = a.progress === null ? '' : ` · ${a.progress}`
  const next = a.nextAction === null ? '' : ` / Next Action: ${a.nextAction} (Due ${a.dueDate})`
  const memo = a.memo === '' ? '' : ` / Memo: ${a.memo}`
  return `${typeName}${progress}${next}${memo}`
}

const same = (a: Content, b: Content): boolean =>
  a.typeId === b.typeId && a.progress === b.progress && a.nextAction === b.nextAction && a.dueDate === b.dueDate && a.memo === b.memo

const pad = (n: number): string => String(n).padStart(2, '0')

/** 인스턴트를 브라우저(로컬) 달력 날짜로 바꾼다. 문자열 날짜 부분은 오프셋에 따라 어긋날 수 있다. */
function localDate(iso: string): string {
  const d = new Date(iso)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

const KEYWORD_MAX = 100

function validateRanges(q: ActionQuery): void {
  // 서버 스키마(max_length=100, 코드 포인트)와 같다. 문구도 서버의 request-validation 문구.
  if (q.keyword !== undefined && Array.from(q.keyword).length > KEYWORD_MAX) throw validation('요청 형식이 올바르지 않습니다')
  if (q.actedFrom && q.actedTo && q.actedFrom > q.actedTo) throw validation('수행일 범위의 시작은 끝보다 늦을 수 없습니다.')
  if (q.dueFrom && q.dueTo && q.dueFrom > q.dueTo) throw validation('Due Date 범위의 시작은 끝보다 늦을 수 없습니다.')
}

function findAction(ctx: MockContext, id: number): ActionRecord {
  const found = ctx.store.data.actions.find((a) => a.id === id)
  if (!found) throw notFound('Action을 찾을 수 없습니다.')
  return found
}

function matches(a: ActionRecord, q: ActionQuery): boolean {
  if (q.typeId && a.typeId !== q.typeId) return false
  if (q.actorId && a.actorId !== q.actorId) return false
  if (q.keyword) {
    const needle = q.keyword.trim().toLowerCase()
    if (![a.progress, a.nextAction, a.memo].some((t) => t !== null && t.toLowerCase().includes(needle))) return false
  }
  const acted = localDate(a.actedAt)
  if (q.actedFrom && acted < q.actedFrom) return false
  if (q.actedTo && acted > q.actedTo) return false
  if (q.dueFrom && (a.dueDate === null || a.dueDate < q.dueFrom)) return false
  if (q.dueTo && (a.dueDate === null || a.dueDate > q.dueTo)) return false
  // 상태 필터가 있으면 Next Action이 없는 Action(상태 null)은 제외된다.
  if (q.nextActionStatus && !(a.nextActionStatus && statusesOf(q.nextActionStatus).includes(a.nextActionStatus))) return false
  return true
}

/** 상태 정렬 순위(서버 `NextActionStatus.sort_rank`): open 0, done 1, notDone 2. */
const STATUS_RANK: Record<NextActionStatus, number> = { open: 0, done: 1, notDone: 2 }

type Sorter = (a: ActionRecord, b: ActionRecord) => number

/** 비교 키. null은 방향과 관계없이 맨 뒤다. 문자열은 소문자로 바꿔 코드 포인트 순(`localeCompare` 쓰지 않음: 서버 COLLATE "C"와 같게). */
function byKey(key: (a: ActionRecord) => string | number | null, order: 'asc' | 'desc'): Sorter {
  const sign = order === 'asc' ? 1 : -1
  return (a, b) => {
    const x = key(a)
    const y = key(b)
    if (x === null || y === null) return x === y ? 0 : x === null ? 1 : -1
    return x === y ? 0 : (x < y ? -1 : 1) * sign
  }
}

/**
 * 서버 정렬 표와 같은 순서. 수행일시 정렬의 동률은 id 오름차순, 그 밖의 정렬은 주 키 -> 수행일시 내림차순 -> id 오름차순이다.
 * 동률 규칙은 방향을 바꿔도 뒤집히지 않는다.
 */
function sorted(rows: ActionRecord[], data: SeedData, q: ActionQuery): ActionRecord[] {
  const byActedDesc: Sorter = (a, b) => compareIso(b.actedAt, a.actedAt) || a.id - b.id
  const order = q.order ?? 'desc'
  const lower = (text: string) => text.toLowerCase()
  const typeName = (a: ActionRecord) => lower(data.actionTypes.find((t) => t.id === a.typeId)?.name ?? String(a.typeId))
  const actorName = (a: ActionRecord) => lower(userRef(data, a.actorId).name)
  const primary: Record<string, Sorter | undefined> = {
    dueDate: byKey((a) => a.dueDate, order),
    actor: byKey(actorName, order),
    type: byKey(typeName, order),
    nextActionStatus: byKey((a) => (a.nextActionStatus === null ? null : STATUS_RANK[a.nextActionStatus]), order),
  }
  if (q.sort === undefined || q.sort === 'actedAt') {
    return rows.sort(order === 'asc' ? (a, b) => compareIso(a.actedAt, b.actedAt) || a.id - b.id : byActedDesc)
  }
  const main = primary[q.sort]
  return rows.sort((a, b) => (main ? main(a, b) : 0) || byActedDesc(a, b))
}

export function createActionsGateway(ctx: MockContext): ActionsGateway {
  return {
    list: (dealCode, query) =>
      read(ctx, () => {
        requireUser(ctx)
        validateRanges(query)
        findDeal(ctx.store.data, dealCode)
        const rows = ctx.store.data.actions.filter((a) => a.dealCode === dealCode && matches(a, query))
        return sorted(rows, ctx.store.data, query).map((a) => actionView(ctx.store.data, a))
      }),
    create: (dealCode, input: ActionInput) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        assertSequenceShape(input.statusChanges ?? []) // 서버 요청 검증(422)은 Deal 조회보다 먼저
        const deal = findDeal(data, dealCode)
        // 서버 순서: Deal(404) → 유형 → 진행사항 → Next Action → Due Date. 새 유형은 모든 검증이 끝난 뒤에만 만든다.
        const typePlan = planActionType(ctx, input.type)
        const content = normalize(input, 0)
        const outcomes = planSequence(ctx, deal, input.statusChanges ?? [])
        const chosen = commitActionType(ctx, typePlan, user.id)
        for (const outcome of outcomes) commitDealChange(ctx, deal, outcome, user.id)
        const record: ActionRecord = {
          id: takeId(data.counters, 'act'),
          dealCode,
          actedAt: ctx.clock.now(),
          actorId: user.id,
          ...content,
          typeId: chosen.id,
          nextActionStatus: content.nextAction === null ? null : 'open',
          nextActionClosedAt: null,
          // 등록 시점(상태 변경이 있으면 적용 후) 값을 저장한다.
          statusKey: deal.statusKey,
          forecastKey: deal.forecastKey,
        }
        data.actions.push(record)
        logHistory(ctx, dealCode, user.id, 'action', 'Action', '', `등록: ${summary(ctx, record)}`)
        return actionView(data, record)
      }),
    update: (actionId, input: ActionUpdateInput) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const record = findAction(ctx, actionId)
        if (!canEditAction(viewerOf(user), record.actorId)) throw forbidden('본인 Action 또는 admin만 수정할 수 있습니다.')
        const typePlan = planActionType(ctx, input.type)
        const next = normalize(input, typePlan.kind === 'existing' ? typePlan.record.id : 0)
        if (same(record, next)) return actionView(ctx.store.data, record)
        const before = summary(ctx, record)
        Object.assign(record, { ...next, typeId: commitActionType(ctx, typePlan, user.id).id })
        // 없던 Next Action을 채우면 Open, 비우면 상태 제거, 있던 것을 고치면 상태는 그대로(종료여도).
        if (record.nextAction === null) Object.assign(record, { nextActionStatus: null, nextActionClosedAt: null })
        else if (record.nextActionStatus === null) Object.assign(record, { nextActionStatus: 'open', nextActionClosedAt: null })
        logHistory(ctx, record.dealCode, user.id, 'action', 'Action', before, `수정: ${summary(ctx, record)}`)
        return actionView(ctx.store.data, record)
      }),
    changeNextActionStatus: (actionId, input: { status: NextActionStatus; memo: string }) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const record = findAction(ctx, actionId)
        if (!canEditAction(viewerOf(user), record.actorId)) throw forbidden(STATUS_FORBIDDEN)
        const note = input.memo.trim()
        if (input.status === 'open' && note !== '') throw validation('Open으로 되돌릴 때는 메모를 남길 수 없습니다.')
        if (record.nextAction === null || record.nextActionStatus === null) throw conflict(NO_NEXT_ACTION)
        const before: NextActionStatus = record.nextActionStatus
        if (before === input.status) throw conflict(`이미 ${STATUS_LABEL[before]} 상태입니다.`)
        const planned = `${record.nextAction} (Due ${record.dueDate}) · ${STATUS_LABEL[before]}`
        record.nextActionStatus = input.status
        record.nextActionClosedAt = input.status === 'open' ? null : ctx.clock.now()
        if (note !== '') record.memo = record.memo === '' ? note : `${record.memo}\n${note}`
        const after = note === '' ? STATUS_LABEL[input.status] : `${STATUS_LABEL[input.status]} / Memo: ${note}`
        logHistory(ctx, record.dealCode, user.id, 'action', 'Next Action', planned, after)
        return actionView(ctx.store.data, record)
      }),
    remove: (actionId) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const record = findAction(ctx, actionId)
        if (!canEditAction(viewerOf(user), record.actorId)) throw forbidden('본인 Action 또는 admin만 삭제할 수 있습니다.')
        const { actions } = ctx.store.data
        actions.splice(actions.indexOf(record), 1)
        logHistory(ctx, record.dealCode, user.id, 'action', 'Action', summary(ctx, record), '삭제')
      }),
  }
}
