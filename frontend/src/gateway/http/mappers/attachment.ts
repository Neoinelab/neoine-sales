import type { Schemas } from '../../../shared/api/client'
import type { Attachment } from '../../../shared/model/types'
import { toUserRef } from './user'

export function toAttachment(row: Schemas['AttachmentResponse']): Attachment {
  return {
    id: row.id,
    dealCode: row.deal_code,
    fileName: row.file_name,
    size: row.size,
    mime: row.mime,
    description: row.description,
    uploadedBy: toUserRef(row.uploaded_by),
    uploadedAt: row.uploaded_at,
  }
}
