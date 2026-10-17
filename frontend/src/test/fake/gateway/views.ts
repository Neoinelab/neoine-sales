/** 저장소 레코드 → 화면용 객체 변환(사용자 풀기, 파생값 계산, 복사본 반환). */

import { compareIso, laterOf } from '../../../shared/model/dates'
import { computeRisk, statusDays } from '../../../shared/model/risk'
import type {
  Attachment,
  Contact,
  ContactRow,
  Deal,
  DealAction,
  DealDetail,
  DealRow,
  HistoryEntry,
  PartnerLinkView,
  User,
  UserRef,
} from '../../../shared/model/types'
import { notFound } from '../errors'
import type { ActionRecord, AttachmentRecord, HistoryRecord, SeedData, UserRecord } from '../store'
import { clone, type MockContext } from './context'

const UNKNOWN_USER: UserRef = { id: '', name: '알 수 없음', role: 'user', status: 'resigned' }

export function userRef(data: SeedData, id: string | null): UserRef {
  const user = data.users.find((u) => u.id === id)
  return user ? { id: user.id, name: user.name, role: user.role, status: user.status } : { ...UNKNOWN_USER, id: id ?? '' }
}

export function userView(data: SeedData, record: UserRecord): User {
  const { createdById, ...rest } = record
  return { ...rest, createdBy: createdById === null ? null : userRef(data, createdById) }
}

export function actionView(data: SeedData, record: ActionRecord): DealAction {
  const { actorId, ...rest } = record
  return { ...rest, actor: userRef(data, actorId) }
}

export function historyView(data: SeedData, record: HistoryRecord): HistoryEntry {
  return {
    id: record.id,
    dealCode: record.dealCode,
    at: record.at,
    by: userRef(data, record.byId),
    category: record.category,
    target: record.target,
    before: record.before,
    after: record.after,
  }
}

export function attachmentView(data: SeedData, record: AttachmentRecord): Attachment {
  return {
    id: record.id,
    dealCode: record.dealCode,
    fileName: record.fileName,
    size: record.size,
    mime: record.mime,
    description: record.description,
    uploadedBy: userRef(data, record.uploadedById),
    uploadedAt: record.uploadedAt,
  }
}

export function findDeal(data: SeedData, code: string): Deal {
  const deal = data.deals.find((d) => d.code === code)
  if (!deal) throw notFound('Deal을 찾을 수 없습니다.')
  return deal
}

/** 연락처를 참조하는 Deal(고객 또는 파트너 링크, 비활성 링크 포함). */
export function dealsOfContact(data: SeedData, contactId: string): Deal[] {
  return data.deals.filter((d) => d.customerContactId === contactId || d.partnerLinks.some((l) => l.contactId === contactId))
}

export function contactRow(data: SeedData, contact: Contact): ContactRow {
  return { ...clone(contact), dealCount: dealsOfContact(data, contact.id).length }
}

/** 수행시각이 가장 늦은 Action(같으면 나중에 만든 것). */
export function latestAction(data: SeedData, dealCode: string): ActionRecord | undefined {
  let best: ActionRecord | undefined
  for (const a of data.actions) {
    if (a.dealCode !== dealCode) continue
    if (!best || compareIso(a.actedAt, best.actedAt) > 0 || (compareIso(a.actedAt, best.actedAt) === 0 && a.id > best.id)) best = a
  }
  return best
}

function contactOf(data: SeedData, id: string): Contact {
  const found = data.contacts.find((c) => c.id === id)
  if (!found) throw notFound('연락처를 찾을 수 없습니다.')
  return found
}

export function dealRow(ctx: MockContext, deal: Deal): DealRow {
  const { data } = ctx.store
  const latest = latestAction(data, deal.code)
  const active = deal.partnerLinks.find((l) => l.active)
  const now = ctx.clock.now()
  const lastUpdatedAt = latest ? laterOf(deal.updatedAt, latest.actedAt) : deal.updatedAt
  const nextAction = latest ? { text: latest.nextAction, dueDate: latest.dueDate } : null
  return {
    ...clone(deal),
    owner: userRef(data, deal.ownerId),
    customer: clone(contactOf(data, deal.customerContactId)),
    activePartner: active ? clone(contactOf(data, active.contactId)) : null,
    nextAction,
    lastUpdatedAt,
    statusDays: statusDays(deal.statusChangedAt, now),
    risk: computeRisk(
      { forecastKey: deal.forecastKey, dueDate: nextAction?.dueDate ?? null, lastUpdatedAt },
      now,
      data.alerts.staleDays,
    ),
  }
}

export function dealDetail(ctx: MockContext, deal: Deal): DealDetail {
  const links = [...deal.partnerLinks].reverse()
  const partnerHistory: PartnerLinkView[] = links
    .sort((a, b) => compareIso(b.linkedAt, a.linkedAt))
    .map(({ contactId, active, linkedAt, unlinkedAt }) => ({
      active,
      linkedAt,
      unlinkedAt,
      contact: clone(contactOf(ctx.store.data, contactId)),
    }))
  return { ...dealRow(ctx, deal), partnerHistory }
}
