import { describe, expect, it } from 'vitest'
import { userRefBody } from '../testHelpers'
import { toAttachment } from './attachment'
import { USER_ID } from '../../../test/fake/seed/ids'

const BODY = {
  id: 7,
  deal_code: '20261017-A001',
  file_name: '견적서.pdf',
  description: '2차 견적',
  size: 2_400_000,
  mime: 'application/pdf',
  uploaded_by: userRefBody(USER_ID.kim, '김영업', false, 'sales'),
  uploaded_at: '2026-10-17T09:30:00+09:00',
}

describe('toAttachment', () => {
  // 테스트 코드: AT-053
  it('서버 응답의 모든 필드를 camelCase 첨부로 바꾼다', () => {
    // when: 서버 응답을 첨부로 바꾼다
    const actual = toAttachment(BODY)

    // then: 모든 필드가 camelCase 이름으로 옮겨진다
    expect(actual).toEqual({
      id: 7,
      dealCode: '20261017-A001',
      fileName: '견적서.pdf',
      description: '2차 견적',
      size: 2_400_000,
      mime: 'application/pdf',
      uploadedBy: { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' },
      uploadedAt: '2026-10-17T09:30:00+09:00',
    })
  })

  // 테스트 코드: AT-053
  it('업로더의 역할과 퇴사 상태를 유지해 삭제 권한 규칙이 동작한다', () => {
    // given: 퇴사한 sales가 올린 응답
    const body = { ...BODY, uploaded_by: userRefBody(USER_ID.old, '강퇴사', true, 'sales') }

    // when: 응답을 첨부로 바꾼다
    const attachment = toAttachment(body)

    // then: 업로더가 role "sales"·status "resigned"로 남는다
    expect(attachment.uploadedBy).toEqual({ id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' })
  })

  // 테스트 코드: AT-053
  it('빈 설명과 0바이트 크기는 그대로 둔다', () => {
    // when: 빈 설명·0바이트 응답을 첨부로 바꾼다
    const actual = toAttachment({ ...BODY, description: '', size: 0 })

    // then: 설명은 ''이고 크기는 0이다
    expect(actual).toMatchObject({ description: '', size: 0 })
  })
})
