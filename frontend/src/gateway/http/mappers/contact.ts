import type { Schemas } from '../../../shared/api/client'
import type { Contact, ContactInput, ContactRow } from '../../../shared/model/types'

/** 등록·수정 본문의 공통 필드. 화면의 빈 직급('')은 서버에서 null이다. */
export function toContactBody(input: ContactInput): Schemas['ContactUpdateRequest'] {
  return {
    company: input.company,
    name: input.name,
    title: input.title === '' ? null : input.title,
    email: input.email,
    phone: input.phone,
  }
}

export function toContact(row: Schemas['ContactResponse']): Contact {
  return {
    id: row.id,
    kind: row.kind,
    company: row.company,
    name: row.name,
    title: row.title ?? '',
    email: row.email,
    phone: row.phone,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export function toContactRow(row: Schemas['ContactRowResponse']): ContactRow {
  return { ...toContact(row), dealCount: row.deal_count }
}
