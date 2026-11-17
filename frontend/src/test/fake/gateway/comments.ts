import type { CommentsGateway } from '../../../gateway/types'
import { forbidden, notFound, requestValidation, validation } from '../errors'
import type { CommentRecord } from '../store'
import {
  COMMENT_ACTION_MISSING,
  COMMENT_DELETE_FORBIDDEN,
  COMMENT_NOT_FOUND,
  COMMENT_READ_FORBIDDEN,
  commentTarget,
  requiredBody,
  storeComment,
} from './commentRules'
import { read, requireUser, requireWrite, write, type MockContext } from './context'
import { logHistory } from './historyLog'
import { commentView, findDeal } from './views'

const DEAL_CODE_FORMAT = /^[0-9]{8}-[A-Z0-9]{4}$/
const MAX_ID = 2 ** 53 - 1
const READ_IDS_MAX = 500

const isId = (value: unknown): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= 1 && value <= MAX_ID

/** 서버 `parse_deal_code`: 형식이 틀린 code는 없는 Deal과 같은 404다. */
function dealOf(ctx: MockContext, code: string) {
  if (!DEAL_CODE_FORMAT.test(code)) throw notFound('Deal을 찾을 수 없습니다.')
  return findDeal(ctx.store.data, code)
}

/** 최근 것이 먼저(작성 시각 내림차순, 같으면 id 내림차순). */
const recentFirst = (a: CommentRecord, b: CommentRecord): number =>
  (a.createdAt === b.createdAt ? 0 : Date.parse(a.createdAt) < Date.parse(b.createdAt) ? 1 : -1) || b.id - a.id

/**
 * 서버 Comment API와 같은 규칙·판정 순서·문구(CM-R3~R12, R26~R29). 수정은 없다.
 * - 작성: 로그인 → user 403 → 요청 형식 422 → 없는 Deal 404 → 본문 422(NUL → 빈 값) → 연결 Action 422.
 * - 삭제: user 403 → 없는 Comment 404 → 작성자·admin이 아니면 403.
 * - 읽음 처리: user 403 → 형식 422 → 없는 Deal 404 → Owner가 아니면 403 → 그 Deal의 읽지 않은 Comment만 채운다(그 밖의 id는 건너뜀).
 */
export function createCommentsGateway(ctx: MockContext): CommentsGateway {
  return {
    list: (dealCode, query = {}) =>
      read(ctx, () => {
        requireUser(ctx)
        const { data } = ctx.store
        dealOf(ctx, dealCode)
        const rows = data.comments.filter((c) => c.dealCode === dealCode && (query.actionId === undefined || c.actionId === query.actionId))
        return rows.sort(recentFirst).map((c) => commentView(data, c))
      }),
    create: (dealCode, input) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        const actionId = input.actionId ?? null
        if (typeof input.body !== 'string' || (actionId !== null && !isId(actionId))) throw requestValidation()
        dealOf(ctx, dealCode)
        const body = requiredBody(input.body)
        if (actionId !== null && !data.actions.some((a) => a.id === actionId && a.dealCode === dealCode)) throw validation(COMMENT_ACTION_MISSING)
        return commentView(data, storeComment(ctx, { dealCode, actionId, authorId: user.id, body }))
      }),
    remove: (commentId) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        const record = data.comments.find((c) => c.id === commentId)
        if (!record) throw notFound(COMMENT_NOT_FOUND)
        // 서버 CM-R12: admin은 모든 Comment, sales는 본인 Comment만(운영 판정 함수와 별개로 서버 규칙을 그대로 둔다).
        if (!(user.role === 'admin' || user.id === record.authorId)) throw forbidden(COMMENT_DELETE_FORBIDDEN)
        const target = commentTarget(ctx, record.actionId)
        data.comments.splice(data.comments.indexOf(record), 1)
        logHistory(ctx, record.dealCode, user.id, 'comment', target, record.body, '삭제')
      }),
    markRead: (dealCode, commentIds) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const { data } = ctx.store
        if (commentIds.length < 1 || commentIds.length > READ_IDS_MAX || !commentIds.every(isId)) throw requestValidation()
        const deal = dealOf(ctx, dealCode)
        if (user.id !== deal.ownerId) throw forbidden(COMMENT_READ_FORBIDDEN)
        const ids = new Set(commentIds)
        const at = ctx.clock.now()
        for (const c of data.comments) if (c.dealCode === dealCode && c.readAt === null && ids.has(c.id)) c.readAt = at
      }),
    counts: (dealCode) =>
      read(ctx, () => {
        requireUser(ctx)
        dealOf(ctx, dealCode)
        const unread = ctx.store.data.comments.filter((c) => c.dealCode === dealCode && c.readAt === null)
        const byAction: Record<number, number> = {}
        for (const c of unread) if (c.actionId !== null) byAction[c.actionId] = (byAction[c.actionId] ?? 0) + 1
        return { unread: unread.length, byAction }
      }),
  }
}
