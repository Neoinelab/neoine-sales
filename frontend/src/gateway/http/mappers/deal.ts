import type { Schemas } from '../../../shared/api/client'
import type { CoChange } from '../../../shared/model/sync'
import type {
  ApplyChangeRequest,
  ContactDraft,
  DealDetail,
  DealInput,
  DealPatch,
  DealRow,
  PartnerLink,
  PartnerLinkView,
} from '../../../shared/model/types'
import { toContact } from './contact'
import { toUserRef } from './user'

function toPartnerLink(link: Schemas['PartnerLinkResponse']): PartnerLink {
  return { contactId: link.contact_id, active: link.active, linkedAt: link.linked_at, unlinkedAt: link.unlinked_at }
}

function toPartnerLinkView(view: Schemas['PartnerHistoryResponse']): PartnerLinkView {
  return { contact: toContact(view.contact), active: view.active, linkedAt: view.linked_at, unlinkedAt: view.unlinked_at }
}

/** 서버 Deal 행 → 화면 DealRow. `risk`·`status_days`는 서버 값을 그대로 쓴다(프런트가 다시 계산하지 않는다). */
export function toDealRow(row: Schemas['DealRowResponse']): DealRow {
  return {
    code: row.code,
    name: row.name,
    ownerId: row.owner_user_id,
    owner: toUserRef(row.owner),
    vendor: row.vendor,
    solution: row.solution,
    users: row.users,
    statusKey: row.status_key,
    forecastKey: row.forecast_key,
    revenueAmount: row.revenue_amount,
    revenueDate: row.revenue_date,
    customerContactId: row.customer.id,
    customer: toContact(row.customer),
    activePartner: row.active_partner === null ? null : toContact(row.active_partner),
    partnerLinks: row.partner_links.map(toPartnerLink),
    quote: { submitted: row.quote.submitted, submittedDate: row.quote.submitted_date },
    poc: { state: row.poc.state, completedDate: row.poc.completed_date },
    procurement: row.procurement,
    bant: { ...row.bant },
    nextAction: row.next_action === null ? null : { text: row.next_action.text, dueDate: row.next_action.due_date },
    lastUpdatedAt: row.last_updated_at,
    statusChangedAt: row.status_changed_at,
    statusDays: row.status_days,
    risk: row.risk,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export function toDealDetail(row: Schemas['DealDetailResponse']): DealDetail {
  return { ...toDealRow(row), partnerHistory: row.partner_history.map(toPartnerLinkView) }
}

export function toCoChange(change: Schemas['CoChangedResponse']): CoChange {
  return { field: change.field === 'status_key' ? 'statusKey' : 'forecastKey', from: change.from, to: change.to }
}

/** 화면의 빈 직급('')은 서버에서 null이다. */
export function toDraftBody(draft: ContactDraft): Schemas['ContactDraftRequest'] {
  return {
    contact_id: draft.contactId,
    company: draft.company,
    name: draft.name,
    title: draft.title === '' ? null : draft.title,
    email: draft.email,
    phone: draft.phone,
  }
}

function quoteBody(quote: DealInput['quote']): Schemas['QuoteRequest'] {
  return { submitted: quote.submitted, submitted_date: quote.submittedDate }
}

function pocBody(poc: DealInput['poc']): Schemas['PocRequest'] {
  return { state: poc.state, completed_date: poc.completedDate }
}

/** 빈 Expected Close는 null로 보내 서버가 자기 문구로 답하게 한다. */
const dateBody = (value: string): string | null => (value === '' ? null : value)

export function toCreateBody(input: DealInput): Schemas['DealCreateRequest'] {
  return {
    name: input.name,
    owner_user_id: input.ownerId,
    vendor: input.vendor,
    solution: input.solution,
    users: input.users,
    status_key: input.statusKey,
    forecast_key: input.forecastKey,
    revenue_amount: input.revenueAmount,
    revenue_date: dateBody(input.revenueDate),
    customer: toDraftBody(input.customer),
    partner: input.partner === null ? null : toDraftBody(input.partner),
    quote: quoteBody(input.quote),
    poc: pocBody(input.poc),
    procurement: input.procurement,
    bant: { ...input.bant },
  }
}

/** 보낸 필드만 담는다(`partner: null`도 보낸 값이다). */
export function toPatchBody(patch: DealPatch): Schemas['DealPatchRequest'] {
  const body: Schemas['DealPatchRequest'] = {}
  if (patch.name !== undefined) body.name = patch.name
  if (patch.ownerId !== undefined) body.owner_user_id = patch.ownerId
  if (patch.vendor !== undefined) body.vendor = patch.vendor
  if (patch.solution !== undefined) body.solution = patch.solution
  if (patch.users !== undefined) body.users = patch.users
  if (patch.statusKey !== undefined) body.status_key = patch.statusKey
  if (patch.forecastKey !== undefined) body.forecast_key = patch.forecastKey
  if (patch.revenueAmount !== undefined) body.revenue_amount = patch.revenueAmount
  if (patch.revenueDate !== undefined) body.revenue_date = dateBody(patch.revenueDate)
  if (patch.customer !== undefined) body.customer = toDraftBody(patch.customer)
  if (patch.partner !== undefined) body.partner = patch.partner === null ? null : toDraftBody(patch.partner)
  if (patch.quote !== undefined) body.quote = quoteBody(patch.quote)
  if (patch.poc !== undefined) body.poc = pocBody(patch.poc)
  if (patch.procurement !== undefined) body.procurement = patch.procurement
  if (patch.bant !== undefined) body.bant = { ...patch.bant }
  return body
}

export function toChangeBody(request: ApplyChangeRequest): Schemas['DealChangeRequest'] {
  const { change, resolution } = request
  const body: Schemas['DealChangeRequest'] = { change: toChangeField(change) }
  if (resolution) {
    body.resolution = {
      revenue_amount: resolution.revenueAmount,
      revenue_date: resolution.revenueDate,
      status_key: resolution.statusKey,
      forecast_key: resolution.forecastKey,
    }
  }
  return body
}

function toChangeField(change: ApplyChangeRequest['change']): Schemas['DealChangeRequest']['change'] {
  switch (change.field) {
    case 'statusKey':
      return { field: 'status_key', value: change.value }
    case 'forecastKey':
      return { field: 'forecast_key', value: change.value }
    case 'revenueAmount':
      return { field: 'revenue_amount', value: change.value }
    case 'revenueDate':
      return { field: 'revenue_date', value: change.value }
  }
}
