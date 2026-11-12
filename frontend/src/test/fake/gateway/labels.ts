import type { LabelsGateway } from '../../../gateway/types'
import { BANT_CATEGORIES, BANT_LABEL_MAX_LENGTH, type BantCategory } from '../../../shared/model/constants'
import type { BantLabelWithUsage } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId, type LabelRecord } from '../store'
import { read, requireAdmin, requireUser, requireWrite, write, type MockContext } from './context'
import { userRef } from './views'

const DUPLICATE_MESSAGE = '같은 구분에 이미 있는 Label 이름입니다.'
const NUL_MESSAGE = 'Label 이름에는 NUL 문자를 쓸 수 없습니다'
const REQUEST_INVALID = '요청 형식이 올바르지 않습니다'

function view(ctx: MockContext, record: LabelRecord): BantLabelWithUsage {
  const { createdById, ...rest } = record
  return {
    ...rest,
    createdBy: createdById === null ? null : userRef(ctx.store.data, createdById),
    usageCount: ctx.store.data.deals.filter((d) => d.bant[record.category] === record.id).length,
  }
}

function find(ctx: MockContext, id: number): LabelRecord {
  const found = ctx.store.data.labels.find((l) => l.id === id)
  if (!found) throw notFound(`BANT Label을(를) 찾을 수 없습니다: ${id}`)
  return found
}

/** 서버 판정 순서: NUL → 앞뒤 공백 제거 → 빈 값 → 길이. 중복 판정은 `ensureUnique`가 따로 한다. */
function normalizeName(raw: string): string {
  if (raw.includes('\0')) throw validation(NUL_MESSAGE)
  const name = raw.trim()
  if (name === '') throw validation('Label 이름을 입력하세요.')
  if (Array.from(name).length > BANT_LABEL_MAX_LENGTH) {
    throw validation(`Label 이름은 ${BANT_LABEL_MAX_LENGTH}자 이내로 입력하세요.`)
  }
  return name
}

function ensureUnique(ctx: MockContext, category: BantCategory, name: string, selfId?: number): void {
  const lower = name.toLowerCase()
  if (ctx.store.data.labels.some((l) => l.category === category && l.id !== selfId && l.name.toLowerCase() === lower)) {
    throw conflict(DUPLICATE_MESSAGE)
  }
}

/** 구분 선언 순 → 기본 Label 먼저(시드 순서) → 직접 만든 Label은 소문자 이름의 UTF-16 단위 순(BMP 밖 문자만 서버의 코드 포인트 순과 다를 수 있음)·id 순. */
function ordered(ctx: MockContext): LabelRecord[] {
  const all = ctx.store.data.labels
  return [...all].sort((a, b) => {
    const byCategory = BANT_CATEGORIES.indexOf(a.category) - BANT_CATEGORIES.indexOf(b.category)
    if (byCategory !== 0) return byCategory
    if (a.isDefault !== b.isDefault) return a.isDefault ? -1 : 1
    if (a.isDefault) return all.indexOf(a) - all.indexOf(b)
    const x = a.name.toLowerCase()
    const y = b.name.toLowerCase()
    if (x !== y) return x < y ? -1 : 1
    return a.id - b.id
  })
}

export function createLabelsGateway(ctx: MockContext): LabelsGateway {
  return {
    list: () =>
      read(ctx, () => {
        requireUser(ctx)
        return ordered(ctx).map((l) => view(ctx, l))
      }),
    create: (category, rawName) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        if (!BANT_CATEGORIES.includes(category)) throw validation(REQUEST_INVALID)
        const name = normalizeName(rawName)
        ensureUnique(ctx, category, name)
        const record: LabelRecord = {
          id: takeId(ctx.store.data.counters, 'lb'),
          category,
          name,
          isDefault: false,
          createdById: user.id,
          createdAt: ctx.clock.now(),
        }
        ctx.store.data.labels.push(record)
        return view(ctx, record)
      }),
    rename: (id, rawName) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const name = normalizeName(rawName) // 서버처럼 이름 오류가 없는 id 404보다 먼저다
        const record = find(ctx, id)
        ensureUnique(ctx, record.category, name, id)
        record.name = name
        return view(ctx, record)
      }),
    remove: (id) =>
      write(ctx, () => {
        requireAdmin(ctx)
        const record = find(ctx, id)
        const usage = view(ctx, record).usageCount
        if (usage > 0) throw conflict(`사용 중인 Label은 삭제할 수 없습니다. (Deal ${usage}건)`)
        const { data } = ctx.store
        data.labels.splice(data.labels.indexOf(record), 1)
      }),
  }
}
