import type { Schemas } from '../../../shared/api/client'
import type { CommentCounts, DealComment } from '../../../shared/model/types'
import { toUserRef } from './user'

/** 서버 Comment → 화면 Comment. 본문은 가공하지 않고, 연결 Action의 `action`은 화면 이름 `progress`가 된다. */
export function toDealComment(row: Schemas['DealCommentResponse']): DealComment {
  return {
    id: row.id,
    dealCode: row.deal_code,
    actionId: row.action_id,
    action: row.action
      ? { id: row.action.id, actedOn: row.action.acted_on, progress: row.action.action, nextAction: row.action.next_action }
      : null,
    body: row.body,
    author: toUserRef(row.author),
    createdAt: row.created_at,
    readAt: row.read_at,
  }
}

/** 읽지 않은 수. `by_action` 배열은 action id를 키로 한 객체가 된다. */
export function toCommentCounts(row: Schemas['DealCommentCounts']): CommentCounts {
  return { unread: row.unread, byAction: Object.fromEntries(row.by_action.map((c) => [c.action_id, c.unread])) }
}
