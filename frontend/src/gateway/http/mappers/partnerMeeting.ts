import type { Schemas } from '../../../shared/api/client'
import type { PartnerMeeting, PartnerMeetingInput, PartnerMeetingSort } from '../../../shared/model/types'
import { toUserRef } from './user'

export function toPartnerMeeting(row: Schemas['PartnerMeetingResponse']): PartnerMeeting {
  return {
    id: row.id,
    partnerCompany: row.partner_company,
    meetingDate: row.meeting_date,
    content: row.content,
    author: toUserRef(row.author),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export function toMeetingBody(input: PartnerMeetingInput): Schemas['MeetingItemRequest'] {
  return { partner_company: input.partnerCompany, meeting_date: input.meetingDate, content: input.content }
}

export function toWireSort(sort: PartnerMeetingSort): Schemas['PartnerMeetingSort'] {
  return sort === 'meetingDate' ? 'meeting_date' : sort
}
