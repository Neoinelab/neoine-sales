/** Action 유형 카탈로그 Fake: 서버 규칙(이름 규칙·대소문자 무시 중복·사용 중 삭제 거부)을 그대로 따른다. */

import type { ActionTypesGateway } from '../../../gateway/types'
import type { CatalogChoice } from '../../../shared/model/catalogChoice'
import type { ActionTypeWithUsage } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId, type ActionTypeRecord } from '../store'
import { read, requireAdmin, requireUser, requireWrite, write, type MockContext } from './context'
import { userRef } from './views'

/** 서버 도메인 값과 같은 길이 한도·문구(Fake가 운영 상수에 기대지 않도록 따로 둔다). */
const NAME_MAX = 50
export const TYPE_REQUIRED_MESSAGE = '유형을 입력하세요.'
export const TYPE_TOO_LONG_MESSAGE = `유형은 ${NAME_MAX}자 이내로 입력하세요.`
export const TYPE_DUPLICATE_MESSAGE = '이미 있는 유형 이름입니다.'
export const UNKNOWN_TYPE_MESSAGE = '선택한 유형이 없습니다. 목록에서 다시 선택하세요.'

export function usageOf(ctx: MockContext, typeId: number): number {
  return ctx.store.data.actions.filter((a) => a.typeId === typeId).length
}

/** 앞뒤 공백 제거 후 빈 값·51자·NUL 거부(Action 요청의 `{name}`도 같은 규칙). */
export function normalizeTypeName(raw: string): string {
  if (raw.includes('\0')) throw validation('유형에 사용할 수 없는 문자가 있습니다.')
  const name = raw.trim()
  if (name === '') throw validation(TYPE_REQUIRED_MESSAGE)
  if (Array.from(name).length > NAME_MAX) throw validation(TYPE_TOO_LONG_MESSAGE)
  return name
}

export function findTypeByName(ctx: MockContext, name: string): ActionTypeRecord | undefined {
  const lower = name.toLowerCase()
  return ctx.store.data.actionTypes.find((t) => t.name.toLowerCase() === lower)
}

/** 기본 유형(시드 순서) 먼저, 직접 만든 유형은 소문자 이름의 코드 포인트 순·id 순. */
function ordered(ctx: MockContext): ActionTypeRecord[] {
  const all = ctx.store.data.actionTypes
  const lowerOf = (t: ActionTypeRecord) => t.name.toLowerCase()
  return [...all].sort((a, b) => {
    if (a.isDefault !== b.isDefault) return a.isDefault ? -1 : 1
    if (a.isDefault) return all.indexOf(a) - all.indexOf(b)
    const x = lowerOf(a)
    const y = lowerOf(b)
    return x < y ? -1 : x > y ? 1 : a.id < b.id ? -1 : 1
  })
}

function view(ctx: MockContext, record: ActionTypeRecord): ActionTypeWithUsage {
  const { createdById, ...rest } = record
  return { ...rest, createdBy: createdById === null ? null : userRef(ctx.store.data, createdById), usageCount: usageOf(ctx, record.id) }
}

function find(ctx: MockContext, id: number): ActionTypeRecord {
  const found = ctx.store.data.actionTypes.find((t) => t.id === id)
  if (!found) throw notFound('Action 유형을 찾을 수 없습니다.')
  return found
}

function checkDuplicate(ctx: MockContext, name: string, selfId?: number): void {
  const lower = name.toLowerCase()
  if (ctx.store.data.actionTypes.some((t) => t.id !== selfId && t.name.toLowerCase() === lower)) {
    throw conflict(TYPE_DUPLICATE_MESSAGE)
  }
}

/** Action 요청의 유형 선택 판정: 저장소는 바꾸지 않는다. 오류는 여기서 던진다. */
export type TypePlan = { kind: 'existing'; record: ActionTypeRecord } | { kind: 'new'; name: string }

export function planActionType(ctx: MockContext, choice: CatalogChoice): TypePlan {
  if ('id' in choice) {
    const record = ctx.store.data.actionTypes.find((t) => t.id === choice.id)
    if (!record) throw validation(UNKNOWN_TYPE_MESSAGE)
    return { kind: 'existing', record }
  }
  const name = normalizeTypeName(choice.name)
  const record = findTypeByName(ctx, name)
  return record ? { kind: 'existing', record } : { kind: 'new', name }
}

/** 검증을 모두 마친 뒤에만 부른다. 새 유형이면 같은 호출 안에서 만든다. */
export function commitActionType(ctx: MockContext, plan: TypePlan, actorId: number): ActionTypeRecord {
  if (plan.kind === 'existing') return plan.record
  const now = ctx.clock.now()
  const record: ActionTypeRecord = {
    id: takeId(ctx.store.data.counters, 'at'),
    name: plan.name,
    isDefault: false,
    createdById: actorId,
    createdAt: now,
    updatedAt: now,
  }
  ctx.store.data.actionTypes.push(record)
  return record
}

export function createActionTypesGateway(ctx: MockContext): ActionTypesGateway {
  return {
    list: () =>
      read(ctx, () => {
        requireUser(ctx)
        return ordered(ctx).map((t) => view(ctx, t))
      }),
    create: (rawName) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const name = normalizeTypeName(rawName)
        checkDuplicate(ctx, name)
        return view(ctx, commitActionType(ctx, { kind: 'new', name }, user.id))
      }),
    rename: (id, rawName) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const name = normalizeTypeName(rawName)
        const record = find(ctx, id)
        checkDuplicate(ctx, name, id)
        record.name = name
        record.updatedAt = ctx.clock.now()
        return view(ctx, record)
      }),
    remove: (id) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const record = find(ctx, id)
        const usage = usageOf(ctx, id)
        if (usage > 0) throw conflict(`사용 중인 유형은 삭제할 수 없습니다. (Action ${usage}건)`)
        const { actionTypes } = ctx.store.data
        actionTypes.splice(actionTypes.indexOf(record), 1)
      }),
  }
}
