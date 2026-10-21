import type { LabelsGateway } from '../../../gateway/types'
import { BANT_CATEGORIES, BANT_LABEL_MAX_LENGTH, type BantCategory } from '../../../shared/model/constants'
import type { BantLabelWithUsage } from '../../../shared/model/types'
import { conflict, notFound, validation } from '../errors'
import { takeId, type LabelRecord } from '../store'
import { read, requireAdmin, requireUser, requireWrite, write, type MockContext } from './context'
import { userRef } from './views'

const DUPLICATE_MESSAGE = '같은 구분에 이미 있는 Label 이름입니다.'

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
  if (!found) throw notFound('Label을 찾을 수 없습니다.')
  return found
}

function checkName(ctx: MockContext, category: BantCategory, raw: string, selfId?: number): string {
  const name = raw.trim()
  if (name === '') throw validation('Label 이름을 입력하세요.')
  if (Array.from(name).length > BANT_LABEL_MAX_LENGTH) {
    throw validation(`Label 이름은 ${BANT_LABEL_MAX_LENGTH}자 이내로 입력하세요.`)
  }
  const lower = name.toLowerCase()
  if (ctx.store.data.labels.some((l) => l.category === category && l.id !== selfId && l.name.toLowerCase() === lower)) {
    throw conflict(DUPLICATE_MESSAGE)
  }
  return name
}

/** 구분 순서 → 기본 Label 먼저(시드 순서) → 직접 만든 Label은 이름순. */
function ordered(ctx: MockContext): LabelRecord[] {
  const all = ctx.store.data.labels
  return [...all].sort((a, b) => {
    const byCategory = BANT_CATEGORIES.indexOf(a.category) - BANT_CATEGORIES.indexOf(b.category)
    if (byCategory !== 0) return byCategory
    if (a.isDefault !== b.isDefault) return a.isDefault ? -1 : 1
    return a.isDefault ? all.indexOf(a) - all.indexOf(b) : a.name.localeCompare(b.name, 'ko')
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
        if (!BANT_CATEGORIES.includes(category)) throw validation('BANT 구분이 올바르지 않습니다.')
        const name = checkName(ctx, category, rawName)
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
        const record = find(ctx, id)
        record.name = checkName(ctx, record.category, rawName, id)
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
