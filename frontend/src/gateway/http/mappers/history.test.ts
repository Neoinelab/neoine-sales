import { describe, expect, it } from 'vitest'
import { CODE, serverHistory, serverUserRef } from '../../../test/fixtures/serverDeal'
import { toHistoryEntry } from './history'

describe('toHistoryEntry', () => {
  it('maps the server entry keeping category, target, before and after as they are', () => {
    expect(toHistoryEntry(serverHistory({ category: 'expectedClose', target: 'Expected Close', before: '2026-12-31', after: '2027-01-31' }))).toEqual({
      id: 'h1',
      dealCode: CODE,
      at: '2026-10-15T09:00:00+09:00',
      by: { id: 'u-kim', name: '김영업', role: 'sales', status: 'active' },
      category: 'expectedClose',
      target: 'Expected Close',
      before: '2026-12-31',
      after: '2027-01-31',
    })
  })

  it('keeps an empty before for the creation entry', () => {
    const entry = toHistoryEntry(serverHistory({ category: 'created', target: 'Deal', before: '', after: 'Deal 등록' }))

    expect(entry).toMatchObject({ category: 'created', before: '', after: 'Deal 등록' })
  })

  it('marks a resigned actor', () => {
    const entry = toHistoryEntry(serverHistory({ by: serverUserRef({ id: 'u-old', resigned: true }) }))

    expect(entry.by.status).toBe('resigned')
  })
})
