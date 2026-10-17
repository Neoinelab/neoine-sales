/** Deal History 자동 기록(R02). 모든 변경은 이 함수들을 거친다. */

import { diffDeal, type HistoryDraft, type HistoryLookup } from '../../../shared/model/history'
import { userLabel } from '../../../shared/model/period'
import type { Deal, HistoryCategory } from '../../../shared/model/types'
import type { CoChange } from '../../../shared/model/sync'
import { nextSeq, takeId } from '../store'
import type { MockContext } from './context'
import { userRef } from './views'

export function lookupFor(ctx: MockContext): HistoryLookup {
  const { data } = ctx.store
  const codeName = (kind: 'status' | 'forecast') => (key: string) =>
    data.codes.find((c) => c.kind === kind && c.key === key)?.name ?? key
  return {
    statusName: codeName('status'),
    forecastName: codeName('forecast'),
    userName: (id) => userLabel(userRef(data, id)),
    contactName: (id) => {
      const c = data.contacts.find((x) => x.id === id)
      return c ? `${c.company} ${c.name}` : id
    },
    bantLabelName: (id) => (id === null ? '선택 안 함' : (data.labels.find((l) => l.id === id)?.name ?? id)),
  }
}

const TARGET_MAX = 300
const TEXT_MAX = 1000

/** 서버와 같이 코드 포인트 기준으로 자른다. 넘으면 앞 N-1자 + '…'(총 N). */
function clip(text: string, max: number): string {
  const points = Array.from(text)
  return points.length <= max ? text : `${points.slice(0, max - 1).join('')}…`
}

/** 한 건 기록. 시각은 시계의 now, 순서는 seq로 보장한다. */
export function logHistory(
  ctx: MockContext,
  dealCode: string,
  byId: string,
  category: HistoryCategory,
  target: string,
  before: string,
  after: string,
): void {
  const { data } = ctx.store
  data.history.push({
    id: takeId(data.counters, 'hi'),
    seq: nextSeq(data.counters),
    dealCode,
    at: ctx.clock.now(),
    byId,
    category,
    target: clip(target, TARGET_MAX),
    before: clip(before, TEXT_MAX),
    after: clip(after, TEXT_MAX),
  })
}

export function logDrafts(ctx: MockContext, dealCode: string, byId: string, drafts: readonly HistoryDraft[]): void {
  for (const d of drafts) logHistory(ctx, dealCode, byId, d.category, d.target, d.before, d.after)
}

/** 변경 전/후 Deal을 비교해 바뀐 필드마다 기록한다. 기록한 건수를 돌려준다. */
export function logDealDiff(
  ctx: MockContext,
  before: Deal,
  after: Deal,
  byId: string,
  coChanged?: readonly Pick<CoChange, 'field'>[],
): number {
  const drafts = diffDeal(before, after, lookupFor(ctx), coChanged)
  logDrafts(ctx, after.code, byId, drafts)
  return drafts.length
}
