import type { CodesGateway } from '../../gateway/types'
import type { Code, CodeKind, CodeSet, CodeWithUsage } from '../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId } from '../store'
import { clone, read, requireAdmin, requireUser, write, type MockContext } from './context'

const LOCKED_MESSAGE = '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.'
const DUPLICATE_MESSAGE = '같은 이름의 코드가 이미 있습니다.'

function ofKind(ctx: MockContext, kind: CodeKind): Code[] {
  return ctx.store.data.codes.filter((c) => c.kind === kind).sort((a, b) => a.order - b.order)
}

function usageOf(ctx: MockContext, code: Code): number {
  const field = code.kind === 'status' ? 'statusKey' : 'forecastKey'
  return ctx.store.data.deals.filter((d) => d[field] === code.key).length
}

function actionUsageOf(ctx: MockContext, code: Code): number {
  const field = code.kind === 'status' ? 'statusKey' : 'forecastKey'
  return ctx.store.data.actions.filter((a) => a[field] === code.key).length
}

function withUsage(ctx: MockContext, code: Code): CodeWithUsage {
  return { ...clone(code), usageCount: usageOf(ctx, code) }
}

function findCode(ctx: MockContext, id: string): Code {
  const found = ctx.store.data.codes.find((c) => c.id === id)
  if (!found) throw notFound('코드를 찾을 수 없습니다.')
  return found
}

function checkName(ctx: MockContext, kind: CodeKind, raw: string, selfId?: string): string {
  const name = raw.trim()
  if (name === '') throw validation('이름을 입력하세요.')
  const lower = name.toLowerCase()
  if (ofKind(ctx, kind).some((c) => c.id !== selfId && c.name.toLowerCase() === lower)) throw conflict(DUPLICATE_MESSAGE)
  return name
}

/** 이름에서 영문 소문자/숫자/밑줄 key를 만든다. 영문이 없으면 `code_<순번>`. 같은 종류 안에서 유일하다. */
function generateKey(ctx: MockContext, kind: CodeKind, name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  const used = new Set(ctx.store.data.codes.filter((c) => c.kind === kind).map((c) => c.key))
  const base = slug === '' ? 'code' : slug
  let key = slug === '' ? `${base}_1` : base
  for (let n = 2; used.has(key); n += 1) key = `${base}_${n}`
  return key
}

export function createCodesGateway(ctx: MockContext): CodesGateway {
  return {
    all: () =>
      read(ctx, (): CodeSet => {
        requireUser(ctx)
        return { statuses: clone(ofKind(ctx, 'status')), forecasts: clone(ofKind(ctx, 'forecast')) }
      }),
    list: (kind) =>
      read(ctx, () => {
        requireAdmin(ctx)
        return ofKind(ctx, kind).map((c) => withUsage(ctx, c))
      }),
    create: (input) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const name = checkName(ctx, input.kind, input.name)
        const siblings = ofKind(ctx, input.kind)
        const code: Code = {
          id: takeId(ctx.store.data.counters, 'cd'),
          kind: input.kind,
          key: generateKey(ctx, input.kind, name),
          name,
          order: (siblings[siblings.length - 1]?.order ?? 0) + 1,
          locked: false,
          outcome: 'open',
          probabilityHint: input.kind === 'forecast' ? (input.probabilityHint ?? null) : null,
        }
        ctx.store.data.codes.push(code)
        return withUsage(ctx, code)
      }),
    rename: (id, rawName) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const code = findCode(ctx, id)
        code.name = checkName(ctx, code.kind, rawName, id)
        return withUsage(ctx, code)
      }),
    reorder: (kind, orderedIds) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const current = ofKind(ctx, kind)
        const valid =
          orderedIds.length === current.length &&
          new Set(orderedIds).size === current.length &&
          current.every((c) => orderedIds.includes(c.id))
        if (!valid) throw validation('순서 목록이 올바르지 않습니다.')
        orderedIds.forEach((id, index) => {
          const code = current.find((c) => c.id === id)
          if (code) code.order = index + 1
        })
        return ofKind(ctx, kind).map((c) => withUsage(ctx, c))
      }),
    remove: (id) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const code = findCode(ctx, id)
        if (code.locked) throw conflict(LOCKED_MESSAGE)
        const deals = usageOf(ctx, code)
        if (deals > 0) throw conflict(`사용 중인 코드는 삭제할 수 없습니다. (Deal ${deals}건)`)
        const actions = actionUsageOf(ctx, code)
        if (actions > 0) throw conflict(`사용 중인 코드는 삭제할 수 없습니다. (Action ${actions}건)`)
        const { data } = ctx.store
        data.codes.splice(data.codes.indexOf(code), 1)
      }),
  }
}
