import type { Schemas } from '../../../shared/api/client'
import type {
  ContractAttachment,
  LicenseContract,
  LicenseContractFields,
  LicenseContractQuery,
  LicenseContractSort,
  LicenseIssueInput,
} from '../../../shared/model/types'
import { toUserRef } from './user'

export function toLicenseContract(row: Schemas['LicenseContractResponse']): LicenseContract {
  return {
    id: row.id,
    dealCode: row.deal_code,
    dealName: row.deal_name,
    dealIsWon: row.deal_is_won,
    customer: row.customer,
    vendor: row.vendor === null ? null : { id: row.vendor.id, name: row.vendor.name },
    product: row.product,
    partner: row.partner,
    salesOwner: toUserRef(row.sales_owner),
    status: row.status,
    licenseStart: row.license_start,
    licenseEnd: row.license_end,
    term: row.term === null ? null : { amount: row.term.amount, unit: row.term.unit },
    techOwner: row.tech_owner,
    inspection: row.inspection_cycle,
    note: row.note,
    renewedFromId: row.renewed_from_id,
    endedAt: row.ended_at,
    attachmentCount: row.attachment_count,
    createdBy: toUserRef(row.created_by),
    updatedBy: toUserRef(row.updated_by),
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  }
}

export function toContractAttachment(row: Schemas['ContractAttachmentResponse']): ContractAttachment {
  return {
    id: row.id,
    contractId: row.contract_id,
    dealCode: row.deal_code,
    fileName: row.file_name,
    size: row.size,
    mime: row.mime,
    description: row.description,
    uploadedBy: toUserRef(row.uploaded_by),
    uploadedAt: row.uploaded_at,
  }
}

const WIRE_SORT: Record<LicenseContractSort, Schemas['LicenseContractSort']> = {
  dealName: 'deal_name',
  customer: 'customer',
  vendor: 'vendor',
  product: 'product',
  partner: 'partner',
  licenseStart: 'license_start',
  licenseEnd: 'license_end',
  status: 'status',
  salesOwner: 'sales_owner',
  techOwner: 'tech_owner',
  inspection: 'inspection',
  note: 'note',
}

/** 값이 있는 조건만 보낸다(서버 기본값을 쓴다). */
export function toContractListParams(query: LicenseContractQuery, offset: number, limit: number) {
  return {
    ...(query.customer ? { customer: query.customer } : {}),
    ...(query.product ? { product: query.product } : {}),
    ...(query.vendorId !== undefined ? { vendor_id: query.vendorId } : {}),
    ...(query.ownerId !== undefined ? { owner_user_id: query.ownerId } : {}),
    ...(query.status ? { status: query.status } : {}),
    ...(query.startFrom ? { start_from: query.startFrom } : {}),
    ...(query.startTo ? { start_to: query.startTo } : {}),
    ...(query.endFrom ? { end_from: query.endFrom } : {}),
    ...(query.endTo ? { end_to: query.endTo } : {}),
    sort: WIRE_SORT[query.sort],
    order: query.order,
    offset,
    limit,
  }
}

export function toFieldsBody(fields: LicenseContractFields): Schemas['LicenseContractFieldsRequest'] {
  return { tech_owner: fields.techOwner, inspection_cycle: fields.inspection, note: fields.note }
}

export function toIssueBody(input: LicenseIssueInput): Schemas['LicenseIssueRequest'] {
  return { ...toFieldsBody(input), start_date: input.start, term_amount: input.term.amount, term_unit: input.term.unit }
}
