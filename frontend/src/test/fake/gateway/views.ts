/** 저장소 레코드 → 화면용 객체 변환(사용자 풀기, 파생값 계산, 복사본 반환). */

import { compareIso } from '../../../shared/model/dates'
import { offsetMinutes } from '../../../shared/model/dates'
import { businessDate } from '../businessDate'
import { computeRisk, statusDays } from '../../../shared/model/risk'
import type {
  Attachment,
  Contact,
  ContactRow,
  Deal,
  DealAction,
  DealComment,
  DealDetail,
  DealRow,
  HistoryEntry,
  PartnerLinkView,
  User,
  UserRef,
} from '../../../shared/model/types'
import { notFound } from '../errors'
import type { ActionRecord, AttachmentRecord, CommentRecord, HistoryRecord, SeedData, UserRecord } from '../store'
import { hasIssuedContract } from './contractWon'
import { pickNextActionBasis } from './nextActionBasis'
import { clone, type MockContext } from './context'

const UNKNOWN_USER: UserRef = { id: 0, name: '알 수 없음', role: 'user', status: 'resigned' }

export function userRef(data: SeedData, id: number | null): UserRef {
  const user = data.users.find((u) => u.id === id)
  return user ? { id: user.id, name: user.name, role: user.role, status: user.status } : { ...UNKNOWN_USER, id: id ?? 0 }
}

export function userView(record: UserRecord): User {
  return { ...record }
}

export function actionView(data: SeedData, record: ActionRecord): DealAction {
  const { actorId, typeId, ...rest } = record
  const type = data.actionTypes.find((t) => t.id === typeId)
  return { ...rest, typeId, type: type?.name ?? String(typeId), actor: userRef(data, actorId) }
}

/** Comment 레코드 → 화면용 객체. 연결 Action 요약은 응답 시점 Action의 현재 값이다(Deal Comment는 null). */
export function commentView(data: SeedData, record: CommentRecord): DealComment {
  const linked = record.actionId === null ? undefined : data.actions.find((a) => a.id === record.actionId)
  return {
    id: record.id,
    dealCode: record.dealCode,
    actionId: record.actionId,
    action: linked ? { id: linked.id, actedOn: linked.actedOn, progress: linked.progress, nextAction: linked.nextAction } : null,
    body: record.body,
    author: userRef(data, record.authorId),
    createdAt: record.createdAt,
    readAt: record.readAt,
  }
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
export function dealsOfContact(data: SeedData, contactId: number): Deal[] {
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
    if (!best || a.actedOn > best.actedOn || (a.actedOn === best.actedOn && a.id > best.id)) best = a
  }
  return best
}

/** RK-R1 기준 행(지난 Open Next Action 우선). 목록·상세의 Next Action, 상태 필터의 기준이다. `today`는 Fake 시계의 업무 날짜. */
export function nextActionBasisOf(data: SeedData, dealCode: string, today: string): ActionRecord | null {
  return pickNextActionBasis(
    data.actions.filter((a) => a.dealCode === dealCode),
    today,
  )
}

function contactOf(data: SeedData, id: number): Contact {
  const found = data.contacts.find((c) => c.id === id)
  if (!found) throw notFound('연락처를 찾을 수 없습니다.')
  return found
}

/** RK-R4: 이 Deal의 Open Next Action 행 가운데 가장 이른 Due(없으면 null). 기준 행과 무관하다. */
export function earliestOpenDue(data: SeedData, dealCode: string): string | null {
  let best: string | null = null
  for (const a of data.actions) {
    if (a.dealCode !== dealCode || a.nextActionStatus !== 'open' || a.dueDate === null) continue
    if (best === null || a.dueDate < best) best = a.dueDate
  }
  return best
}

export function dealRow(ctx: MockContext, deal: Deal): DealRow {
  const { data } = ctx.store
  const latest = latestAction(data, deal.code)
  const active = deal.partnerLinks.find((l) => l.active)
  const now = ctx.clock.now()
  // E4: 모든 Action의 최근 수행일, 없으면 업무 시간대 기준 Deal 등록일(RK-067). Deal 수정(updatedAt)은 반영하지 않는다.
  const lastUpdatedOn = latest ? latest.actedOn : businessDate(deal.createdAt, offsetMinutes(now))
  const basis = nextActionBasisOf(data, deal.code, ctx.clock.today())
  const nextAction =
    basis && basis.nextAction !== null && basis.dueDate !== null && basis.nextActionStatus !== null
      ? { text: basis.nextAction, dueDate: basis.dueDate, status: basis.nextActionStatus, actionId: basis.id }
      : null
  const { vendorId, ...rest } = clone(deal)
  const vendor = data.vendors.find((v) => v.id === vendorId)
  // CM-R47: Deal Owner 기준으로 읽지 않은(readAt이 없는) 이 Deal의 Comment 수. 서버와 같은 값이다.
  const unreadCommentCount = data.comments.filter((c) => c.dealCode === deal.code && c.readAt === null).length
  return {
    ...rest,
    unreadCommentCount,
    vendor: vendor ? { id: vendor.id, name: vendor.name } : null,
    owner: userRef(data, deal.ownerId),
    customer: clone(contactOf(data, deal.customerContactId)),
    activePartner: active ? clone(contactOf(data, active.contactId)) : null,
    hasIssuedLicenseContract: hasIssuedContract(data, deal.code),
    licenseContractCount: data.licenseContracts.filter((c) => c.dealCode === deal.code).length,
    nextAction,
    lastUpdatedOn,
    statusDays: statusDays(deal.statusChangedOn, now),
    risk: computeRisk(
      { forecastKey: deal.forecastKey, statusKey: deal.statusKey, earliestOpenDue: earliestOpenDue(data, deal.code), lastUpdatedOn },
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
