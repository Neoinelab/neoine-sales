import { api } from '../../shared/api/client'
import type { CommentsGateway } from '../types'
import { toCommentCounts, toDealComment } from './mappers/comment'
import { unwrap, unwrapVoid } from './request'

export function createCommentsHttp(): CommentsGateway {
  const byDeal = (code: string) => ({ params: { path: { code } } })
  return {
    list: async (dealCode, query = {}) => {
      const result = await unwrap(
        api.GET('/api/v1/deals/{code}/comments', {
          params: { path: { code: dealCode }, query: query.actionId === undefined ? {} : { action_id: query.actionId } },
        }),
      )
      return result.items.map(toDealComment)
    },
    create: async (dealCode, input) =>
      toDealComment(
        await unwrap(
          api.POST('/api/v1/deals/{code}/comments', {
            ...byDeal(dealCode),
            body: { body: input.body, ...(input.actionId === undefined ? {} : { action_id: input.actionId }) },
          }),
        ),
      ),
    remove: (commentId) => unwrapVoid(api.DELETE('/api/v1/deal-comments/{comment_id}', { params: { path: { comment_id: commentId } } })),
    markRead: (dealCode, commentIds) =>
      unwrapVoid(api.POST('/api/v1/deals/{code}/comment-reads', { ...byDeal(dealCode), body: { comment_ids: [...commentIds] } })),
    counts: async (dealCode) => toCommentCounts(await unwrap(api.GET('/api/v1/deals/{code}/comment-counts', byDeal(dealCode)))),
  }
}
