import type { CodesGateway } from '../../../gateway/types'
import type { Code, CodeKind, CodeSet, CodeWithUsage } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId } from '../store'
import { clone, read, requireAdmin, requireUser, write, type MockContext } from './context'

const LOCKED_MESSAGE = '시스템과 연결된 코드는 삭제할 수 없습니다. 이름과 순서는 변경할 수 있습니다.'
const DUPLICATE_MESSAGE = '같은 이름의 코드가 이미 있습니다.'
const NAME_MAX = 50
const HINT_MAX = 20
const KEY_MAX = 50

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

function findCode(ctx: MockContext, id: number): Code {
  const found = ctx.store.data.codes.find((c) => c.id === id)
  if (!found) throw notFound(`코드을(를) 찾을 수 없습니다: ${id}`)
  return found
}

/** 글자 수는 서버(파이썬)처럼 코드 포인트 기준이다. */
function lengthOf(text: string): number {
  return [...text].length
}

/** 이름 형식 검사(서버 순서: NUL → 앞뒤 공백 제거 후 빈 값 → 50자 초과). 중복은 따로 본다. */
function normalizeName(raw: string): string {
  if (raw.includes('\u0000')) throw validation('이름에는 NUL 문자를 쓸 수 없습니다')
  const name = raw.trim()
  if (name === '') throw validation('이름을 입력하세요.')
  if (lengthOf(name) > NAME_MAX) throw validation(`이름은 ${NAME_MAX}자 이내로 입력하세요.`)
  return name
}

/** 같은 종류 안에서 대소문자를 무시한 이름 중복(자기 자신 제외)이면 409. */
function ensureUniqueName(ctx: MockContext, kind: CodeKind, name: string, selfId?: number): void {
  const lower = name.toLowerCase()
  if (ofKind(ctx, kind).some((c) => c.id !== selfId && c.name.toLowerCase() === lower)) throw conflict(DUPLICATE_MESSAGE)
}

/** 확률 힌트(등록 때만): NUL 거절 → 앞뒤 공백 제거, 빈 값은 없음 → Status면 거절 → 20자 초과 거절. */
function normalizeHint(kind: CodeKind, raw: string | null | undefined): string | null {
  if (raw === null || raw === undefined) return null
  if (raw.includes('\u0000')) throw validation('확률 힌트에는 NUL 문자를 쓸 수 없습니다')
  const hint = raw.trim()
  if (hint === '') return null
  if (kind === 'status') throw validation('Status에는 확률 힌트를 둘 수 없습니다.')
  if (lengthOf(hint) > HINT_MAX) throw validation(`확률 힌트는 ${HINT_MAX}자 이내로 입력하세요.`)
  return hint
}

/**
 * 이름에서 영문 소문자/숫자/밑줄 key를 만든다(서버 `generate_key`와 같다). 영문·숫자가 없으면 쓰지 않은 가장 작은
 * `code_<N>`, 숫자로 시작하면 `c_` 접두, 50자로 자르고, 같은 종류에 있으면 `_2`, `_3`…(접미사 포함 50자 이하).
 */
function generateKey(ctx: MockContext, kind: CodeKind, name: string): string {
  const slug = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
  const used = new Set(ctx.store.data.codes.filter((c) => c.kind === kind).map((c) => c.key))
  if (slug === '') {
    let n = 1
    while (used.has(`code_${n}`)) n += 1
    return `code_${n}`
  }
  const base = (/^[0-9]/.test(slug) ? `c_${slug}` : slug).slice(0, KEY_MAX)
  let key = base
  for (let n = 2; used.has(key); n += 1) {
    const suffix = `_${n}`
    key = base.slice(0, KEY_MAX - suffix.length) + suffix
  }
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
        const name = normalizeName(input.name)
        ensureUniqueName(ctx, input.kind, name)
        const probabilityHint = normalizeHint(input.kind, input.probabilityHint)
        const siblings = ofKind(ctx, input.kind)
        const code: Code = {
          id: takeId(ctx.store.data.counters, 'cd'),
          kind: input.kind,
          key: generateKey(ctx, input.kind, name),
          name,
          order: (siblings[siblings.length - 1]?.order ?? 0) + 1,
          locked: false,
          outcome: 'open',
          probabilityHint,
        }
        ctx.store.data.codes.push(code)
        return withUsage(ctx, code)
      }),
    rename: (id, rawName) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const name = normalizeName(rawName)
        const code = findCode(ctx, id)
        ensureUniqueName(ctx, code.kind, name, id)
        code.name = name
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
