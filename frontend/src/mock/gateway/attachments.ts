import type { AttachmentsGateway, UploadResult } from '../../gateway/types'
import { compareIso } from '../../shared/model/dates'
import { STORAGE_UNAVAILABLE_MESSAGE, validateUpload } from '../../shared/model/fileRules'
import { canDeleteAttachment } from '../../shared/model/permissions'
import { fileExists, forbidden, notFound, storageUnavailable, validation } from '../errors'
import { takeId, type AttachmentRecord } from '../store'
import { read, requireUser, requireWrite, viewerOf, write, type MockContext } from './context'
import { logHistory } from './historyLog'
import { attachmentView, findDeal, userRef } from './views'

function find(ctx: MockContext, id: string): AttachmentRecord {
  const found = ctx.store.data.attachments.find((a) => a.id === id)
  if (!found) throw notFound('첨부 파일을 찾을 수 없습니다.')
  return found
}

export function createAttachmentsGateway(ctx: MockContext): AttachmentsGateway {
  return {
    list: (dealCode) =>
      read(ctx, () => {
        requireUser(ctx)
        const { data } = ctx.store
        findDeal(data, dealCode)
        return data.attachments
          .filter((a) => a.dealCode === dealCode)
          .sort((a, b) => compareIso(b.uploadedAt, a.uploadedAt) || b.id.localeCompare(a.id))
          .map((a) => attachmentView(data, a))
      }),
    upload: (dealCode, input) =>
      write(ctx, (): UploadResult => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        const deal = findDeal(data, dealCode)
        const ruleError = validateUpload(input.file, input.description)
        if (ruleError) throw validation(ruleError.message)
        if (ctx.store.storageFailure) throw storageUnavailable(STORAGE_UNAVAILABLE_MESSAGE)

        const { file } = input
        const existing = data.attachments.find((a) => a.dealCode === dealCode && a.fileName === file.name)
        if (existing && input.onExists === 'ask') throw fileExists(file.name)
        if (existing && input.onExists === 'skip') return { outcome: 'skipped' }

        const now = ctx.clock.now()
        const fields = {
          size: file.size,
          mime: file.type || 'application/octet-stream',
          description: input.description,
          uploadedById: user.id,
          uploadedAt: now,
          content: file as Blob,
        }
        const record = existing
          ? Object.assign(existing, fields)
          : { id: takeId(data.counters, 'att'), dealCode, fileName: file.name, ...fields }
        if (!existing) data.attachments.push(record)
        deal.updatedAt = now
        logHistory(ctx, dealCode, user.id, 'attachment', '첨부 파일', '', `${existing ? '교체' : '업로드'} ${file.name}`)
        return { outcome: existing ? 'replaced' : 'uploaded', attachment: attachmentView(data, record) }
      }),
    remove: (attachmentId) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        const record = find(ctx, attachmentId)
        const uploader = userRef(ctx.store.data, record.uploadedById)
        if (!canDeleteAttachment(viewerOf(user), uploader)) throw forbidden('본인이 올린 파일만 삭제할 수 있습니다.')
        const { data } = ctx.store
        data.attachments.splice(data.attachments.indexOf(record), 1)
        const deal = data.deals.find((d) => d.code === record.dealCode)
        if (deal) deal.updatedAt = ctx.clock.now()
        logHistory(ctx, record.dealCode, user.id, 'attachment', '첨부 파일', '', `삭제 ${record.fileName}`)
      }),
    download: (attachmentId) =>
      read(ctx, () => {
        requireUser(ctx)
        const record = find(ctx, attachmentId)
        const blob = typeof record.content === 'string' ? new Blob([record.content], { type: 'text/plain' }) : record.content
        return { fileName: record.fileName, blob }
      }),
  }
}
