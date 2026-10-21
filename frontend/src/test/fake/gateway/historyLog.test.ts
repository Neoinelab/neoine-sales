/** R-12: mock `logHistory`도 서버 HistoryDraft처럼 target 300자, before·after 1,000자(코드 포인트)로 자른다(초과 시 앞 N-1자 + "…"). */

import { describe, expect, it } from 'vitest'
import { createClock } from '../clock'
import type { MockStore } from '../store'
import type { MockContext } from './context'
import { logHistory } from './historyLog'
import { USER_ID } from '../seed/ids'

function context(): MockContext {
  const store = { data: { history: [], counters: {} }, session: { userId: USER_ID.kim }, storageFailure: false }
  return { store: store as unknown as MockStore, clock: createClock('2026-10-15T09:00:00+09:00') } as MockContext
}

function logged(ctx: MockContext, target: string, before: string, after: string) {
  logHistory(ctx, '20261015-A001', USER_ID.kim, 'action', target, before, after)
  const rows = ctx.store.data.history
  const last = rows[rows.length - 1]
  if (!last) throw new Error('nothing logged')
  return last
}

const points = (text: string): number => Array.from(text).length

describe('logHistory clipping', () => {
  it('keeps before and after of exactly 1,000 code points', () => {
    const entry = logged(context(), 'Action', 'a'.repeat(1000), 'b'.repeat(1000))

    expect(entry.before).toBe('a'.repeat(1000))
    expect(entry.after).toBe('b'.repeat(1000))
  })

  it('cuts 1,001 code points to the first 999 plus an ellipsis', () => {
    const entry = logged(context(), 'Action', 'a'.repeat(1001), 'b'.repeat(1001))

    expect(entry.before).toBe(`${'a'.repeat(999)}…`)
    expect(entry.after).toBe(`${'b'.repeat(999)}…`)
    expect(points(entry.after)).toBe(1000)
  })

  it('counts an emoji as one code point and never splits it', () => {
    const entry = logged(context(), 'Action', '😀'.repeat(1500), '😀'.repeat(1000))

    expect(entry.before).toBe(`${'😀'.repeat(999)}…`)
    expect(entry.after).toBe('😀'.repeat(1000))
  })

  it('cuts the target at 300 code points the same way', () => {
    const keep = logged(context(), 't'.repeat(300), '', 'x')
    const cut = logged(context(), 't'.repeat(301), '', 'x')

    expect(keep.target).toBe('t'.repeat(300))
    expect(cut.target).toBe(`${'t'.repeat(299)}…`)
  })

  it('leaves short texts and empty strings as they are', () => {
    const entry = logged(context(), 'Status', '', '등록: 짧은 문구')

    expect(entry).toMatchObject({ target: 'Status', before: '', after: '등록: 짧은 문구' })
  })
})
