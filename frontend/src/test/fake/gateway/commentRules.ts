/** Comment 규칙(서버 CM-R1·R13·R26과 같은 문구·순서). 테스트용 Fake 전용. */

import { validation } from '../errors'
import { takeId, type CommentRecord } from '../store'
import type { MockContext } from './context'
import { logHistory } from './historyLog'

export const COMMENT_NUL = 'Comment에는 NUL 문자를 쓸 수 없습니다'
export const COMMENT_EMPTY = 'Comment를 입력하세요.'
export const COMMENT_ACTION_MISSING = '선택한 Action이 이 Deal에 없습니다.'
export const COMMENT_NOT_FOUND = 'Comment를 찾을 수 없습니다.'
export const COMMENT_DELETE_FORBIDDEN = '본인 Comment 또는 admin만 삭제할 수 있습니다.'
export const COMMENT_READ_FORBIDDEN = 'Deal Owner만 Comment를 읽음 처리할 수 있습니다.'

/** 본문 규칙 1: NUL이 있으면 422(빈 값 판정보다 먼저). 통과하면 앞뒤 공백을 지운 값(공백뿐이면 ''). */
export function trimmedBody(raw: string): string {
  if (raw.includes('\u0000')) throw validation(COMMENT_NUL)
  return raw.trim()
}

/** 필수 본문(작성 API): 비면 422. */
export function requiredBody(raw: string): string {
  const body = trimmedBody(raw)
  if (body === '') throw validation(COMMENT_EMPTY)
  return body
}

/** 이력 대상: Deal Comment는 "Comment", Action Comment는 "Action Comment (<수행일> <유형 이름>)". */
export function commentTarget(ctx: MockContext, actionId: number | null): string {
  if (actionId === null) return 'Comment'
  const { data } = ctx.store
  const action = data.actions.find((a) => a.id === actionId)
  if (!action) return 'Comment'
  const type = data.actionTypes.find((t) => t.id === action.typeId)?.name ?? String(action.typeId)
  return `Action Comment (${action.actedOn} ${type})`
}

/**
 * Comment를 저장하고 이력("등록: <본문>")을 남긴다. 작성자가 그 순간의 Deal Owner이면 읽음(`readAt` = 작성 시각)으로 생긴다.
 * 본문은 이미 검사·trim된 값이어야 한다.
 */
export function storeComment(ctx: MockContext, input: { dealCode: string; actionId: number | null; authorId: number; body: string }): CommentRecord {
  const { data } = ctx.store
  const owner = data.deals.find((d) => d.code === input.dealCode)?.ownerId
  const now = ctx.clock.now()
  const record: CommentRecord = {
    id: takeId(data.counters, 'cm'),
    dealCode: input.dealCode,
    actionId: input.actionId,
    authorId: input.authorId,
    body: input.body,
    createdAt: now,
    readAt: owner === input.authorId ? now : null,
  }
  data.comments.push(record)
  logHistory(ctx, input.dealCode, input.authorId, 'comment', commentTarget(ctx, input.actionId), '', `등록: ${input.body}`)
  return record
}
