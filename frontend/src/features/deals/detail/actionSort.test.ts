import { describe, expect, it } from 'vitest'
import type { ActionSortKey } from '../../../shared/model/types'
import { DEFAULT_ACTION_SORT, nextActionSort } from './actionSort'

describe('DEFAULT_ACTION_SORT', () => {
  // 기본 정렬은 수행일시 내림차순(최신순)이다.
  // 테스트 코드: NA-063
  it('starts with the acted time, newest first', () => {
    // when·then: 기본 정렬 값을 읽으면 수행일시 내림차순이다.
    expect(DEFAULT_ACTION_SORT).toEqual({ sort: 'actedAt', order: 'desc' })
  })
})

describe('nextActionSort', () => {
  // 다른 열을 고르면 자연 방향(수행일시 내림차순, 나머지 오름차순)으로 시작한다.
  // 테스트 코드: NA-063
  it.each([
    ['actedAt', 'desc'],
    ['dueDate', 'asc'],
    ['actor', 'asc'],
    ['type', 'asc'],
    ['nextActionStatus', 'asc'],
  ] as const)('starts a new column %s in its natural order %s', (key, order) => {
    // given: 다른 열로 정렬한 상태다.
    const from = key === 'actor' ? { sort: 'type', order: 'desc' } : { sort: 'actor', order: 'desc' }

    // when·then: 새 열을 고르면 그 열의 자연 방향이 된다.
    expect(nextActionSort(from as never, key)).toEqual({ sort: key, order })
  })

  // 같은 열을 다시 고르면 방향이 바뀐다.
  // 테스트 코드: NA-063
  it.each(['actedAt', 'dueDate', 'actor', 'type', 'nextActionStatus'] as ActionSortKey[])(
    'flips the direction when the same column %s is chosen again',
    (key) => {
      // when: 오름차순·내림차순 상태에서 같은 열을 다시 고른다.
      const asc = nextActionSort({ sort: key, order: 'asc' }, key)
      const desc = nextActionSort({ sort: key, order: 'desc' }, key)

      // then: 방향이 서로 반대로 바뀐다.
      expect(asc).toEqual({ sort: key, order: 'desc' })
      expect(desc).toEqual({ sort: key, order: 'asc' })
    },
  )

  // 다른 열 뒤 수행일시를 고르면 다시 내림차순으로 시작한다.
  // 테스트 코드: NA-063
  it('returns to the natural order of the acted time after another column', () => {
    // given: 기본 정렬에서 Due Date를 골랐다.
    const afterDue = nextActionSort(DEFAULT_ACTION_SORT, 'dueDate')

    // then: Due Date는 오름차순이다.
    expect(afterDue).toEqual({ sort: 'dueDate', order: 'asc' })
    // when·then: 수행일시를 고르면 내림차순으로 돌아온다.
    expect(nextActionSort(afterDue, 'actedAt')).toEqual({ sort: 'actedAt', order: 'desc' })
  })

  // 정렬 상태를 바꿔도 입력 객체는 바뀌지 않는다.
  it('does not change its input', () => {
    // given: 담당자 오름차순 정렬 상태다.
    const current = { sort: 'actor', order: 'asc' } as const

    // when: 같은 열을 다시 골라 다음 상태를 만든다.
    nextActionSort(current, 'actor')

    // then: 원래 상태 객체는 그대로다.
    expect(current).toEqual({ sort: 'actor', order: 'asc' })
  })
})
