import { describe, expect, it } from 'vitest'
import { latestWithNextAction } from './nextActionBasis'
import type { DealAction } from './types'

/** 서버 기준 행 정의와 같다: Next Action이 있는 가장 최근 Action(수행일시 내림차순, 같으면 id 내림차순). */

function action(id: number, actedAt: string, nextAction: string | null): DealAction {
  return {
    id,
    dealCode: '20261016-AB12',
    actedAt,
    actor: { id: 2, name: '김영업', role: 'sales', status: 'active' },
    type: '미팅',
    typeId: 1,
    progress: '진행',
    nextAction,
    dueDate: nextAction === null ? null : '2026-11-01',
    nextActionStatus: nextAction === null ? null : 'open',
    nextActionClosedAt: null,
    memo: '',
    statusKey: 'prospecting',
    forecastKey: 'pipeline',
  }
}

describe('latestWithNextAction', () => {
  it('picks the most recently acted row that has a next action', () => {
    const rows = [action(1, '2026-10-01T09:00:00+09:00', '첫째'), action(2, '2026-10-03T09:00:00+09:00', '셋째'), action(3, '2026-10-02T09:00:00+09:00', '둘째')]

    expect(latestWithNextAction(rows)?.id).toBe(2)
  })

  it('does not depend on the order of the list', () => {
    const rows = [action(1, '2026-10-01T09:00:00+09:00', '첫째'), action(2, '2026-10-03T09:00:00+09:00', '셋째')]

    expect(latestWithNextAction([...rows].reverse())?.id).toBe(2)
  })

  it('breaks ties of the same acted time by the higher id', () => {
    const same = '2026-10-01T09:00:00+09:00'
    const rows = [action(5, same, '낮은 id'), action(9, same, '높은 id'), action(7, same, '가운데')]

    expect(latestWithNextAction(rows)?.id).toBe(9)
    expect(latestWithNextAction([...rows].reverse())?.id).toBe(9)
  })

  it('skips newer rows without a next action', () => {
    const rows = [action(1, '2026-10-01T09:00:00+09:00', '이전'), action(2, '2026-10-05T09:00:00+09:00', null)]

    expect(latestWithNextAction(rows)?.id).toBe(1)
  })

  it('compares acted times as instants, not as strings with different offsets', () => {
    // 09:00+09:00 = 00:00Z 이므로 00:30Z가 더 늦다
    const rows = [action(1, '2026-10-01T09:00:00+09:00', '서울'), action(2, '2026-10-01T00:30:00+00:00', 'UTC')]

    expect(latestWithNextAction(rows)?.id).toBe(2)
  })

  it('includes closed rows (state does not matter)', () => {
    const closed = { ...action(2, '2026-10-05T09:00:00+09:00', '종료됨'), nextActionStatus: 'done' as const, nextActionClosedAt: '2026-10-06T09:00:00+09:00' }

    expect(latestWithNextAction([action(1, '2026-10-01T09:00:00+09:00', '이전'), closed])?.id).toBe(2)
  })

  it('returns null when no row has a next action', () => {
    expect(latestWithNextAction([action(1, '2026-10-01T09:00:00+09:00', null)])).toBeNull()
  })

  it('returns null for an empty list', () => {
    expect(latestWithNextAction([])).toBeNull()
  })

  it('does not change the given list', () => {
    const rows = [action(1, '2026-10-01T09:00:00+09:00', '첫째'), action(2, '2026-10-03T09:00:00+09:00', '셋째')]
    const copy = rows.map((r) => r.id)

    latestWithNextAction(rows)

    expect(rows.map((r) => r.id)).toEqual(copy)
  })
})
