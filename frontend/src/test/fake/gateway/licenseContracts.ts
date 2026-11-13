import type { ContractUploadResult, LicenseContractsGateway } from '../../../gateway/types'
import { businessToday } from '../businessDate'
import { STORAGE_UNAVAILABLE_MESSAGE, validateUpload } from '../../../shared/model/fileRules'
import { FORECAST_WON } from '../../../shared/model/constants'
import { licenseEnd } from '../../../shared/model/licensePeriod'
import { canDeleteAttachment, isAdmin } from '../../../shared/model/permissions'
import type { LicenseContractFields, LicenseIssueInput } from '../../../shared/model/types'
import { conflict, fileExists, forbidden, notFound, storageUnavailable, validation } from '../errors'
import { takeId, type ContractAttachmentRecord, type LicenseContractRecord } from '../store'
import { read, requireUser, requireWrite, viewerOf, write, type MockContext } from './context'
import { matchesContract, sortContracts, validateContractQuery } from './contractSearch'
import { DEAL_NOT_WON } from './contractWon'
import { contractAttachmentView, contractView } from './contractViews'
import { userRef } from './views'

const TECH_OWNER_MAX = 100
const NOTE_MAX = 2000
const TERM_MIN = 1
const TERM_MAX = 99
const DATE = /^\d{4}-\d{2}-\d{2}$/
const INSPECTIONS = ['monthly', 'quarterly', 'semiannual', 'yearly', 'none']

const NOT_FOUND = '라이선스 계약을 찾을 수 없습니다.'
const NOT_ISSUED_ONLY = '미발급 계약만 발급할 수 있습니다.'
const ISSUED_ONLY = '발급 상태 계약만 갱신할 수 있습니다.'
const ALREADY_ENDED = '이미 종료된 계약입니다.'
const ALREADY_ISSUED = '이 Deal에는 이미 발급 상태인 라이선스 계약이 있습니다.'
const DELETE_ADMIN_ONLY = '계약 삭제는 관리자만 할 수 있습니다.'

const isIssued = (record: LicenseContractRecord): boolean => record.status === 'issued_new' || record.status === 'issued_renewal'
const length = (text: string): number => Array.from(text).length

function find(ctx: MockContext, id: number): LicenseContractRecord {
  const found = ctx.store.data.licenseContracts.find((c) => c.id === id)
  if (!found) throw notFound(NOT_FOUND)
  return found
}

/** 계약 칸 검증. 앞뒤 공백은 정리해 저장한다. */
function checkedFields(fields: LicenseContractFields): LicenseContractFields {
  const techOwner = fields.techOwner.trim()
  const note = fields.note.trim()
  if (length(techOwner) > TECH_OWNER_MAX) throw validation(`기술담당은 ${TECH_OWNER_MAX}자 이내로 입력하세요.`)
  if (length(note) > NOTE_MAX) throw validation(`Note는 ${NOTE_MAX}자 이내로 입력하세요.`)
  if (!INSPECTIONS.includes(fields.inspection)) throw validation('점검주기가 올바르지 않습니다.')
  return { techOwner, inspection: fields.inspection, note }
}

function checkedTerm(input: LicenseIssueInput) {
  const { amount, unit } = input.term
  if (!DATE.test(input.start)) throw validation('라이선스 시작일을 입력하세요.')
  if (!Number.isInteger(amount) || amount < TERM_MIN || amount > TERM_MAX) throw validation(`기간은 ${TERM_MIN}~${TERM_MAX} 사이로 입력하세요.`)
  return { amount, unit }
}

function applyIssue(record: LicenseContractRecord, input: LicenseIssueInput, status: 'issued_new' | 'issued_renewal'): void {
  const term = checkedTerm(input)
  Object.assign(record, {
    status,
    licenseStart: input.start,
    licenseEnd: licenseEnd(input.start, term.amount, term.unit),
    term,
  })
}

function assertDealWon(ctx: MockContext, record: LicenseContractRecord): void {
  const deal = ctx.store.data.deals.find((d) => d.code === record.dealCode)
  if (deal && deal.forecastKey !== FORECAST_WON) throw conflict(DEAL_NOT_WON)
}

function assertNoOtherIssued(ctx: MockContext, record: LicenseContractRecord): void {
  const other = ctx.store.data.licenseContracts.some((c) => c.dealCode === record.dealCode && c.id !== record.id && isIssued(c))
  if (other) throw conflict(ALREADY_ISSUED)
}

function createAttachmentsGateway(ctx: MockContext): LicenseContractsGateway['attachments'] {
  const findFile = (id: number): ContractAttachmentRecord => {
    const found = ctx.store.data.contractAttachments.find((a) => a.id === id)
    if (!found) throw notFound('첨부 파일을 찾을 수 없습니다.')
    return found
  }
  return {
    list: (contractId) =>
      read(ctx, () => {
        requireUser(ctx)
        const { data } = ctx.store
        find(ctx, contractId)
        return data.contractAttachments
          .filter((a) => a.contractId === contractId)
          .sort((a, b) => (a.uploadedAt < b.uploadedAt ? 1 : a.uploadedAt > b.uploadedAt ? -1 : b.id - a.id))
          .map((a) => contractAttachmentView(data, a))
      }),
    upload: (contractId, input) =>
      write(ctx, (): ContractUploadResult => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        const contract = find(ctx, contractId)
        const ruleError = validateUpload(input.file, input.description)
        if (ruleError) throw validation(ruleError.message)
        if (ctx.store.storageFailure) throw storageUnavailable(STORAGE_UNAVAILABLE_MESSAGE)

        const { file } = input
        const fileName = file.name.normalize('NFC')
        const existing = data.contractAttachments.find((a) => a.contractId === contractId && a.fileName === fileName)
        if (existing && input.onExists === 'ask') throw fileExists(fileName)
        if (existing && input.onExists === 'skip') return { outcome: 'skipped' }
        if (existing && !canDeleteAttachment(viewerOf(user), userRef(data, existing.uploadedById))) {
          throw forbidden('본인이 올린 파일만 교체할 수 있습니다.')
        }
        const fields = {
          size: file.size,
          mime: file.type || 'application/octet-stream',
          description: input.description.trim(),
          uploadedById: user.id,
          uploadedAt: ctx.clock.now(),
          content: file as Blob,
        }
        const record = existing ? Object.assign(existing, fields) : { id: takeId(data.counters, 'lca'), contractId: contract.id, fileName, ...fields }
        if (!existing) data.contractAttachments.push(record)
        return { outcome: existing ? 'replaced' : 'uploaded', attachment: contractAttachmentView(data, record) }
      }),
    remove: (attachmentId) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        const record = findFile(attachmentId)
        if (!canDeleteAttachment(viewerOf(user), userRef(data, record.uploadedById))) throw forbidden('본인이 올린 파일만 삭제할 수 있습니다.')
        data.contractAttachments.splice(data.contractAttachments.indexOf(record), 1)
      }),
    download: (attachmentId) =>
      read(ctx, () => {
        requireUser(ctx)
        const record = findFile(attachmentId)
        const blob = typeof record.content === 'string' ? new Blob([record.content], { type: 'text/plain' }) : record.content
        return { fileName: record.fileName, blob }
      }),
  }
}

export function createLicenseContractsGateway(ctx: MockContext): LicenseContractsGateway {
  const touch = (record: LicenseContractRecord, byId: number): void => {
    record.updatedById = byId
    record.updatedAt = ctx.clock.now()
  }
  return {
    list: (query, offset, limit) =>
      read(ctx, () => {
        requireUser(ctx)
        validateContractQuery(query)
        const { data } = ctx.store
        const matched = sortContracts(data, data.licenseContracts.filter((c) => matchesContract(data, c, query)), query)
        return { items: matched.slice(offset, offset + limit).map((c) => contractView(data, c)), total: matched.length, offset, limit }
      }),
    get: (id) =>
      read(ctx, () => {
        requireUser(ctx)
        return contractView(ctx.store.data, find(ctx, id))
      }),
    update: (id, fields) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const record = find(ctx, id)
        Object.assign(record, checkedFields(fields))
        touch(record, user.id)
        return contractView(ctx.store.data, record)
      }),
    issue: (id, input) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const record = find(ctx, id)
        assertDealWon(ctx, record)
        const fields = checkedFields(input)
        if (record.status !== 'not_issued') throw conflict(NOT_ISSUED_ONLY)
        assertNoOtherIssued(ctx, record)
        applyIssue(record, input, 'issued_new')
        Object.assign(record, fields)
        touch(record, user.id)
        return contractView(ctx.store.data, record)
      }),
    renew: (id, input) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        const previous = find(ctx, id)
        assertDealWon(ctx, previous)
        const fields = checkedFields(input)
        if (!isIssued(previous)) throw conflict(ISSUED_ONLY)
        const now = ctx.clock.now()
        const renewal: LicenseContractRecord = {
          id: takeId(data.counters, 'lc'),
          dealCode: previous.dealCode,
          ...(previous.dealSide ? { dealSide: previous.dealSide } : {}),
          status: 'issued_renewal',
          licenseStart: null,
          licenseEnd: null,
          term: null,
          ...fields,
          renewedFromId: previous.id,
          endedOn: null,
          createdById: user.id,
          updatedById: user.id,
          createdAt: now,
          updatedAt: now,
        }
        applyIssue(renewal, input, 'issued_renewal')
        Object.assign(previous, { status: 'ended', endedOn: businessToday(now) })
        touch(previous, user.id)
        data.licenseContracts.push(renewal)
        return contractView(data, renewal)
      }),
    end: (id) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const record = find(ctx, id)
        if (record.status === 'ended') throw conflict(ALREADY_ENDED)
        Object.assign(record, { status: 'ended', endedOn: businessToday(ctx.clock.now()) })
        touch(record, user.id)
        return contractView(ctx.store.data, record)
      }),
    remove: (id) =>
      write(ctx, () => {
        // 서버 판정 순서(LC-R15·R28): user는 읽기 전용 403, 그다음 admin이 아니면 계약 존재와 무관하게 403, 없는 계약 404는 admin만.
        const user = requireWrite(ctx)
        if (!isAdmin(user.role)) throw forbidden(DELETE_ADMIN_ONLY)
        const { data } = ctx.store
        const record = find(ctx, id)
        data.licenseContracts.splice(data.licenseContracts.indexOf(record), 1)
        data.contractAttachments = data.contractAttachments.filter((a) => a.contractId !== id)
        // 갱신 원본이 지워지면 이 행을 가리키던 renewedFromId는 비운다(서버 ON DELETE SET NULL).
        for (const other of data.licenseContracts) if (other.renewedFromId === id) other.renewedFromId = null
      }),
    attachments: createAttachmentsGateway(ctx),
  }
}
