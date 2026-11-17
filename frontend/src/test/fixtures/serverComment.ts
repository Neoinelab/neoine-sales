/** HTTP Comment 어댑터·매퍼 테스트용 서버 응답 조각(생성 타입 기준, 더미 값). */

import type { Schemas } from '../../shared/api/client'
import { CODE, serverUserRef } from './serverDeal'

export const COMMENT_ID = 71

export function serverComment(over: Partial<Schemas['DealCommentResponse']> = {}): Schemas['DealCommentResponse'] {
  return {
    id: COMMENT_ID,
    deal_code: CODE,
    action_id: null,
    action: null,
    body: '예산 회의 예정',
    author: serverUserRef(),
    created_at: '2026-11-12T09:30:00+09:00',
    updated_at: '2026-11-12T09:30:00+09:00',
    read_at: null,
    ...over,
  }
}
