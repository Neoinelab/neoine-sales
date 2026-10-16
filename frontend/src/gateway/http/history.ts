import { api } from '../../shared/api/client'
import type { HistoryGateway } from '../types'
import { toHistoryEntry } from './mappers/history'
import { unwrap } from './request'

export function createHistoryHttp(): HistoryGateway {
  return {
    // 서버가 최신순으로 준다. 순서를 바꾸지 않는다.
    list: async (dealCode, query) =>
      (
        await unwrap(
          api.GET('/api/v1/deals/{code}/history', {
            params: { path: { code: dealCode }, query: query.category ? { category: query.category } : {} },
          }),
        )
      ).map(toHistoryEntry),
  }
}
