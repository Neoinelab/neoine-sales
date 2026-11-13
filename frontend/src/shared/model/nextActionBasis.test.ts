import { describe, expect, it } from 'vitest'
import { latestWithNextAction } from './nextActionBasis'
import type { DealAction } from './types'

/** 서버 기준 행 정의와 같다: Next Action이 있는 가장 최근 Action(수행일 내림차순, 같으면 id 내림차순). */

function action(id: number, actedOn: string, nextAction: string | null): DealAction {
  return {
    id,
    dealCode: '20261016-AB12',
    actedOn,
    actor: { id: 2, name: '김영업', role: 'sales', status: 'active' },
    type: '미팅',
    typeId: 1,
    progress: '진행',
    nextAction,
    dueDate: nextAction === null ? null : '2026-11-01',
    nextActionStatus: nextAction === null ? null : 'open',
    nextActionClosedOn: null,
    memo: '',
    statusKey: 'prospecting',
    forecastKey: 'pipeline',
  }
}

describe('latestWithNextAction', () => {
  // Next Action이 있는 가장 최근 수행 행을 고른다.
  // 테스트 코드: AC-081
  it('picks the most recently acted row that has a next action', () => {
    // given: 수행 시각이 다른 Next Action 행 세 건
    const rows = [action(1, '2026-10-01', '첫째'), action(2, '2026-10-03', '셋째'), action(3, '2026-10-02', '둘째')]

    // when·then: 기준 행을 고르면 가장 최근 행이다
    expect(latestWithNextAction(rows)?.id).toBe(2)
  })

  // 목록의 순서에 영향받지 않는다.
  // 테스트 코드: AC-081
  it('does not depend on the order of the list', () => {
    // given: 두 행
    const rows = [action(1, '2026-10-01', '첫째'), action(2, '2026-10-03', '셋째')]

    // when·then: 뒤집은 목록에서도 같은 행을 고른다
    expect(latestWithNextAction([...rows].reverse())?.id).toBe(2)
  })

  // 수행일이 같으면 id가 큰 행을 고른다.
  // 테스트 코드: AC-081
  it('breaks ties of the same acted day by the higher id', () => {
    // given: 같은 수행일의 세 행
    const same = '2026-10-01'
    const rows = [action(5, same, '낮은 id'), action(9, same, '높은 id'), action(7, same, '가운데')]

    // when·then: id가 가장 큰 행을 고르고 목록을 뒤집어도 같다
    expect(latestWithNextAction(rows)?.id).toBe(9)
    expect(latestWithNextAction([...rows].reverse())?.id).toBe(9)
  })

  // Next Action이 없는 더 최근 행은 건너뛴다.
  // 테스트 코드: AC-081
  it('skips newer rows without a next action', () => {
    // given: 이전 Next Action 행과 더 최근의 진행사항만 행
    const rows = [action(1, '2026-10-01', '이전'), action(2, '2026-10-05', null)]

    // when·then: Next Action이 있는 이전 행을 고른다
    expect(latestWithNextAction(rows)?.id).toBe(1)
  })

  // 수행 시각은 문자열이 아니라 순간으로 비교한다.
  // 테스트 코드: AC-081
  it('compares acted days as plain dates, a later day wins over a higher id', () => {
    // given: 수행일이 하루 늦은 낮은 id 행과 하루 이른 높은 id 행
    const rows = [action(9, '2026-10-01', '높은 id'), action(2, '2026-10-02', '다음 날')]

    // when·then: id와 관계없이 더 늦은 수행일의 행을 고른다
    expect(latestWithNextAction(rows)?.id).toBe(2)
  })

  // 종료된 행도 기준 행에 들어간다(상태는 상관없다).
  // 테스트 코드: AC-081
  it('includes closed rows (state does not matter)', () => {
    // given: 더 최근의 종료(수행) 행
    const closed = { ...action(2, '2026-10-05', '종료됨'), nextActionStatus: 'done' as const, nextActionClosedOn: '2026-10-06' }

    // when·then: 종료된 행을 고른다
    expect(latestWithNextAction([action(1, '2026-10-01', '이전'), closed])?.id).toBe(2)
  })

  // Next Action이 있는 행이 없으면 없음이다.
  // 테스트 코드: AC-081
  it('returns null when no row has a next action', () => {
    // when·then: 진행사항만 행뿐이면 null이다
    expect(latestWithNextAction([action(1, '2026-10-01', null)])).toBeNull()
  })

  // 빈 목록이면 없음이다.
  // 테스트 코드: AC-081
  it('returns null for an empty list', () => {
    // when·then: 빈 목록이면 null이다
    expect(latestWithNextAction([])).toBeNull()
  })

  // 받은 목록을 바꾸지 않는다.
  // 테스트 코드: AC-081
  it('does not change the given list', () => {
    // given: 두 행과 id 순서의 복사본
    const rows = [action(1, '2026-10-01', '첫째'), action(2, '2026-10-03', '셋째')]
    const copy = rows.map((r) => r.id)

    // when: 기준 행을 고른다
    latestWithNextAction(rows)

    // then: 목록의 순서가 그대로다
    expect(rows.map((r) => r.id)).toEqual(copy)
  })
})
