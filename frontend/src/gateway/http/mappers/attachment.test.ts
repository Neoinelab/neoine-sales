import { describe, expect, it } from 'vitest'
import { userRefBody } from '../testHelpers'
import { toAttachment } from './attachment'

const BODY = {
  id: 'a1b2',
  deal_code: '20261017-A001',
  file_name: '견적서.pdf',
  description: '2차 견적',
  size: 2_400_000,
  mime: 'application/pdf',
  uploaded_by: userRefBody('u-kim', '김영업', false, 'sales'),
  uploaded_at: '2026-10-17T09:30:00+09:00',
}

describe('toAttachment', () => {
  it('renames every field to the camelCase Attachment', () => {
    expect(toAttachment(BODY)).toEqual({
      id: 'a1b2',
      dealCode: '20261017-A001',
      fileName: '견적서.pdf',
      description: '2차 견적',
      size: 2_400_000,
      mime: 'application/pdf',
      uploadedBy: { id: 'u-kim', name: '김영업', role: 'sales', status: 'active' },
      uploadedAt: '2026-10-17T09:30:00+09:00',
    })
  })

  it('keeps the uploader role and a resigned status so the delete permission rule works', () => {
    const attachment = toAttachment({ ...BODY, uploaded_by: userRefBody('u-old', '강퇴사', true, 'sales') })

    expect(attachment.uploadedBy).toEqual({ id: 'u-old', name: '강퇴사', role: 'sales', status: 'resigned' })
  })

  it('keeps an empty description and a zero byte size as they are', () => {
    expect(toAttachment({ ...BODY, description: '', size: 0 })).toMatchObject({ description: '', size: 0 })
  })
})
