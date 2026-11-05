import { api } from '../../shared/api/client'
import type { LicenseContractsGateway } from '../types'
import { fileNameFromDisposition } from './contentDisposition'
import { toContractAttachment, toContractListParams, toFieldsBody, toIssueBody, toLicenseContract } from './mappers/licenseContract'
import { malformedResponse, settle, unwrap, unwrapVoid } from './request'

export function createLicenseContractsHttp(): LicenseContractsGateway {
  const path = (id: number) => ({ params: { path: { contract_id: id } } })
  return {
    list: async (query, offset, limit) => {
      const page = await unwrap(api.GET('/api/v1/license-contracts', { params: { query: toContractListParams(query, offset, limit) } }))
      return { items: page.items.map(toLicenseContract), total: page.total, offset: page.offset, limit: page.limit }
    },
    get: async (id) => toLicenseContract(await unwrap(api.GET('/api/v1/license-contracts/{contract_id}', path(id)))),
    update: async (id, fields) =>
      toLicenseContract(await unwrap(api.PUT('/api/v1/license-contracts/{contract_id}', { ...path(id), body: toFieldsBody(fields) }))),
    issue: async (id, input) =>
      toLicenseContract(await unwrap(api.POST('/api/v1/license-contracts/{contract_id}/issue', { ...path(id), body: toIssueBody(input) }))),
    renew: async (id, input) =>
      toLicenseContract(await unwrap(api.POST('/api/v1/license-contracts/{contract_id}/renewal', { ...path(id), body: toIssueBody(input) }))),
    end: async (id) => toLicenseContract(await unwrap(api.POST('/api/v1/license-contracts/{contract_id}/end', path(id)))),
    remove: (id) => unwrapVoid(api.DELETE('/api/v1/license-contracts/{contract_id}', path(id))),
    attachments: {
      list: async (contractId) => {
        const body = await unwrap(api.GET('/api/v1/license-contracts/{contract_id}/attachments', path(contractId)))
        return body.items.map(toContractAttachment)
      },
      upload: async (contractId, input) => {
        // 파일·설명은 가공하지 않고 보낸다(trim과 검증은 서버 몫). Content-Type은 브라우저가 boundary와 함께 정한다.
        const form = new FormData()
        form.append('file', input.file, input.file.name)
        form.append('description', input.description)
        form.append('on_exists', input.onExists)
        const result = await unwrap(
          api.POST('/api/v1/license-contracts/{contract_id}/attachments', {
            ...path(contractId),
            body: { description: input.description, on_exists: input.onExists },
            bodySerializer: () => form,
          }),
        )
        if (result.outcome === 'skipped') return { outcome: 'skipped' }
        if (result.attachment === null) throw malformedResponse()
        return { outcome: result.outcome, attachment: toContractAttachment(result.attachment) }
      },
      remove: (attachmentId) =>
        unwrapVoid(api.DELETE('/api/v1/license-contract-attachments/{attachment_id}', { params: { path: { attachment_id: attachmentId } } })),
      download: async (attachmentId) => {
        const { data, response } = await settle(
          api.GET('/api/v1/license-contract-attachments/{attachment_id}/download', {
            params: { path: { attachment_id: attachmentId } },
            parseAs: 'blob',
          }),
        )
        return {
          fileName: fileNameFromDisposition(response.headers.get('Content-Disposition')),
          blob: data instanceof Blob ? data : new Blob([]),
        }
      },
    },
  }
}
