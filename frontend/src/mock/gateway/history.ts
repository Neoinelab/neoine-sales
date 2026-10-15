import type { HistoryGateway } from '../../gateway/types'
import { compareIso } from '../../shared/model/dates'
import { read, requireUser, type MockContext } from './context'
import { findDeal, historyView } from './views'

export function createHistoryGateway(ctx: MockContext): HistoryGateway {
  return {
    list: (dealCode, query) =>
      read(ctx, () => {
        requireUser(ctx)
        const { data } = ctx.store
        findDeal(data, dealCode)
        return data.history
          .filter((h) => h.dealCode === dealCode && (query.category ? h.category === query.category : true))
          .sort((a, b) => compareIso(b.at, a.at) || b.seq - a.seq)
          .map((h) => historyView(data, h))
      }),
  }
}
