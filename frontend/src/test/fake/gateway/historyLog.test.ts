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
  // 변경 전·후가 정확히 1,000자면 그대로 둔다.
  // 테스트 코드: DD-117
  it('keeps before and after of exactly 1,000 code points', () => {
    // when: 이력을 기록한다 (전제: 1,000자 전·후)
    const entry = logged(context(), 'Action', 'a'.repeat(1000), 'b'.repeat(1000))

    // then: 잘리지 않는다
    expect(entry.before).toBe('a'.repeat(1000))
    expect(entry.after).toBe('b'.repeat(1000))
  })

  // 1,001자는 앞 999자 + '…'로 자른다.
  // 테스트 코드: DD-117
  it('cuts 1,001 code points to the first 999 plus an ellipsis', () => {
    // when: 이력을 기록한다 (전제: 1,001자 전·후)
    const entry = logged(context(), 'Action', 'a'.repeat(1001), 'b'.repeat(1001))

    // then: 앞 999자 + '…'이고 1,000 코드 포인트다
    expect(entry.before).toBe(`${'a'.repeat(999)}…`)
    expect(entry.after).toBe(`${'b'.repeat(999)}…`)
    expect(points(entry.after)).toBe(1000)
  })

  // 이모지는 코드 포인트 하나로 세고 쪼개지 않는다.
  // 테스트 코드: DD-117
  it('counts an emoji as one code point and never splits it', () => {
    // when: 이력을 기록한다 (전제: 이모지 1,500개·1,000개)
    const entry = logged(context(), 'Action', '😀'.repeat(1500), '😀'.repeat(1000))

    // then: 999개 + '…'와 1,000개 그대로다
    expect(entry.before).toBe(`${'😀'.repeat(999)}…`)
    expect(entry.after).toBe('😀'.repeat(1000))
  })

  // 대상은 300자에서 같은 방식으로 자른다.
  // 테스트 코드: DD-117
  it('cuts the target at 300 code points the same way', () => {
    // given: 300자와 301자 대상
    const keep = logged(context(), 't'.repeat(300), '', 'x')
    // when: 이력을 기록한다
    const cut = logged(context(), 't'.repeat(301), '', 'x')

    // then: 300자는 그대로, 301자는 299자 + '…'다
    expect(keep.target).toBe('t'.repeat(300))
    expect(cut.target).toBe(`${'t'.repeat(299)}…`)
  })

  // 짧은 글과 빈 문자열은 그대로 둔다.
  // 테스트 코드: DD-117
  it('leaves short texts and empty strings as they are', () => {
    // when: 이력을 기록한다 (전제: 짧은 문구)
    const entry = logged(context(), 'Status', '', '등록: 짧은 문구')

    // then: 값이 그대로다
    expect(entry).toMatchObject({ target: 'Status', before: '', after: '등록: 짧은 문구' })
  })
})
