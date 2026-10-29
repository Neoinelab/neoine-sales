import type { Schemas } from '../../../shared/api/client'
import type { PartnerDealOption, PartnerMeeting, PartnerMeetingInput, PartnerMeetingSort } from '../../../shared/model/types'
import { toUserRef } from './user'

export function toPartnerMeeting(row: Schemas['PartnerMeetingResponse']): PartnerMeeting {
  return {
    id: row.id,
    partnerCompany: row.partner_company,
    deal: { code: row.deal.code, name: row.deal.name },
    meetingDate: row.meeting_date,
    content: row.content,
    author: toUserRef(row.author),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export function toMeetingBody(input: PartnerMeetingInput): Schemas['MeetingItemRequest'] {
  return { partner_company: input.partnerCompany, deal_code: input.dealCode, meeting_date: input.meetingDate, content: input.content }
}

export function toWireSort(sort: PartnerMeetingSort): Schemas['PartnerMeetingSort'] {
  return sort === 'meetingDate' ? 'meeting_date' : sort
}

export function toDealOption(row: Schemas['DealOptionResponse']): PartnerDealOption {
  return { code: row.code, name: row.name, customerCompany: row.customer_company }
}
