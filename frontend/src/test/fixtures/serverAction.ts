/** HTTP Action 어댑터·매퍼 테스트용 서버 응답 조각(생성 타입 기준, 더미 값). */

import type { Schemas } from '../../shared/api/client'
import { CODE, serverUserRef } from './serverDeal'

export const ACTION_TYPE_ID = '3c1f9a6e-2b84-4e0d-8a57-6d9e1b7c4f20'
export const ACTION_ID = '5b0f3c1e-7a52-4d6e-9c1a-2f4b8a6d0e11'

export function serverAction(over: Partial<Schemas['DealActionResponse']> = {}): Schemas['DealActionResponse'] {
  return {
    id: ACTION_ID,
    deal_code: CODE,
    action_type: { id: ACTION_TYPE_ID, name: '미팅' },
    action: '고객사 방문',
    next_action: '견적 재전달',
    due_date: '2026-10-22',
    memo: '',
    acted_at: '2026-10-15T09:00:00+09:00',
    actor: serverUserRef(),
    status_key: 'prospecting',
    forecast_key: 'pipeline',
    created_at: '2026-10-15T09:00:00+09:00',
    updated_at: '2026-10-15T09:00:00+09:00',
    ...over,
  }
}
