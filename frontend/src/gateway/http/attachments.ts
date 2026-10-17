import { api } from '../../shared/api/client'
import type { AttachmentsGateway } from '../types'
import { fileNameFromDisposition } from './contentDisposition'
import { toAttachment } from './mappers/attachment'
import { malformedResponse, settle, unwrap, unwrapVoid } from './request'

export function createAttachmentsHttp(): AttachmentsGateway {
  return {
    list: async (dealCode) => {
      const body = await unwrap(api.GET('/api/v1/deals/{code}/attachments', { params: { path: { code: dealCode } } }))
      return body.items.map(toAttachment)
    },
    upload: async (dealCode, input) => {
      // 파일·설명은 가공하지 않고 보낸다(trim과 검증은 서버 몫). Content-Type은 브라우저가 boundary와 함께 정한다.
      const form = new FormData()
      form.append('file', input.file, input.file.name)
      form.append('description', input.description)
      form.append('on_exists', input.onExists)
      const result = await unwrap(
        api.POST('/api/v1/deals/{code}/attachments', {
          params: { path: { code: dealCode } },
          body: { description: input.description, on_exists: input.onExists },
          bodySerializer: () => form,
        }),
      )
      if (result.outcome === 'skipped') return { outcome: 'skipped' }
      if (result.attachment === null) throw malformedResponse()
      return { outcome: result.outcome, attachment: toAttachment(result.attachment) }
    },
    remove: (attachmentId) =>
      unwrapVoid(api.DELETE('/api/v1/attachments/{attachment_id}', { params: { path: { attachment_id: attachmentId } } })),
    download: async (attachmentId) => {
      const { data, response } = await settle(
        api.GET('/api/v1/attachments/{attachment_id}/download', {
          params: { path: { attachment_id: attachmentId } },
          parseAs: 'blob',
        }),
      )
      return {
        fileName: fileNameFromDisposition(response.headers.get('Content-Disposition')),
        blob: data instanceof Blob ? data : new Blob([]),
      }
    },
  }
}
