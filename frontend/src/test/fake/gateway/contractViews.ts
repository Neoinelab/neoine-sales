/** 라이선스 계약 레코드 → 화면용 객체. Deal에서 오는 5칸은 읽을 때마다 Deal에서 풀어 온다(Deal이 바뀌면 계약 행 값도 바뀐다). */

import { FORECAST_WON } from '../../../shared/model/constants'
import type { ContractAttachment, LicenseContract, NamedRef, UserRef } from '../../../shared/model/types'
import type { ContractAttachmentRecord, ContractDealSide, LicenseContractRecord, SeedData } from '../store'
import { userRef } from './views'

/** 계약 행에 보일 Deal 쪽 값. */
export interface DealSideView {
  dealName: string
  /** Deal이 Won인가(시드의 Deal 밖 과거 계약은 true). */
  isWon: boolean
  customer: string
  vendor: NamedRef | null
  product: string
  partner: string | null
  owner: UserRef
}

function vendorOf(data: SeedData, id: number | null): NamedRef | null {
  const vendor = data.vendors.find((v) => v.id === id)
  return vendor ? { id: vendor.id, name: vendor.name } : null
}

function fromSide(data: SeedData, side: ContractDealSide): DealSideView {
  return {
    dealName: side.dealName,
    isWon: true,
    customer: side.customer,
    vendor: vendorOf(data, side.vendorId),
    product: side.product,
    partner: side.partner,
    owner: userRef(data, side.ownerId),
  }
}

/** Deal이 있으면 Deal 값, 없는 시드 계약이면 계약이 들고 있는 값. */
export function dealSideOf(data: SeedData, record: LicenseContractRecord): DealSideView {
  const deal = data.deals.find((d) => d.code === record.dealCode)
  if (!deal) {
    if (record.dealSide) return fromSide(data, record.dealSide)
    return { dealName: record.dealCode, isWon: true, customer: '', vendor: null, product: '', partner: null, owner: userRef(data, null) }
  }
  const company = (contactId: number) => data.contacts.find((c) => c.id === contactId)?.company ?? ''
  const active = deal.partnerLinks.find((l) => l.active)
  return {
    dealName: deal.name,
    isWon: deal.forecastKey === FORECAST_WON,
    customer: company(deal.customerContactId),
    vendor: vendorOf(data, deal.vendorId),
    product: deal.product,
    partner: active ? company(active.contactId) : null,
    owner: userRef(data, deal.ownerId),
  }
}

export function contractView(data: SeedData, record: LicenseContractRecord): LicenseContract {
  const side = dealSideOf(data, record)
  return {
    id: record.id,
    dealCode: record.dealCode,
    dealName: side.dealName,
    dealIsWon: side.isWon,
    customer: side.customer,
    vendor: side.vendor,
    product: side.product,
    partner: side.partner,
    salesOwner: side.owner,
    status: record.status,
    licenseStart: record.licenseStart,
    licenseEnd: record.licenseEnd,
    term: record.term === null ? null : { ...record.term },
    techOwner: record.techOwner,
    inspection: record.inspection,
    note: record.note,
    renewedFromId: record.renewedFromId,
    endedOn: record.endedOn,
    attachmentCount: data.contractAttachments.filter((a) => a.contractId === record.id).length,
    createdBy: userRef(data, record.createdById),
    updatedBy: userRef(data, record.updatedById),
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
  }
}

export function contractAttachmentView(data: SeedData, record: ContractAttachmentRecord): ContractAttachment {
  const contract = data.licenseContracts.find((c) => c.id === record.contractId)
  return {
    id: record.id,
    contractId: record.contractId,
    dealCode: contract?.dealCode ?? '',
    fileName: record.fileName,
    size: record.size,
    mime: record.mime,
    description: record.description,
    uploadedBy: userRef(data, record.uploadedById),
    uploadedAt: record.uploadedAt,
  }
}
