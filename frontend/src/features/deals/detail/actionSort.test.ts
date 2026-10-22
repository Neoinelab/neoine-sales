import { describe, expect, it } from 'vitest'
import type { ActionSortKey } from '../../../shared/model/types'
import { DEFAULT_ACTION_SORT, nextActionSort } from './actionSort'

describe('DEFAULT_ACTION_SORT (AC3)', () => {
  it('starts with the acted time, newest first', () => {
    expect(DEFAULT_ACTION_SORT).toEqual({ sort: 'actedAt', order: 'desc' })
  })
})

describe('nextActionSort (AC4)', () => {
  it.each([
    ['actedAt', 'desc'],
    ['dueDate', 'asc'],
    ['actor', 'asc'],
    ['type', 'asc'],
    ['nextActionStatus', 'asc'],
  ] as const)('starts a new column %s in its natural order %s', (key, order) => {
    const from = key === 'actor' ? { sort: 'type', order: 'desc' } : { sort: 'actor', order: 'desc' }

    expect(nextActionSort(from as never, key)).toEqual({ sort: key, order })
  })

  it.each(['actedAt', 'dueDate', 'actor', 'type', 'nextActionStatus'] as ActionSortKey[])(
    'flips the direction when the same column %s is chosen again',
    (key) => {
      const asc = nextActionSort({ sort: key, order: 'asc' }, key)
      const desc = nextActionSort({ sort: key, order: 'desc' }, key)

      expect(asc).toEqual({ sort: key, order: 'desc' })
      expect(desc).toEqual({ sort: key, order: 'asc' })
    },
  )

  it('returns to the natural order of the acted time after another column', () => {
    const afterDue = nextActionSort(DEFAULT_ACTION_SORT, 'dueDate')

    expect(afterDue).toEqual({ sort: 'dueDate', order: 'asc' })
    expect(nextActionSort(afterDue, 'actedAt')).toEqual({ sort: 'actedAt', order: 'desc' })
  })

  it('does not change its input', () => {
    const current = { sort: 'actor', order: 'asc' } as const

    nextActionSort(current, 'actor')

    expect(current).toEqual({ sort: 'actor', order: 'asc' })
  })
})
