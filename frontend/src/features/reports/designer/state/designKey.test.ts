import { describe, expect, it } from 'vitest'
import type { ReportQueryInput } from '../../../../shared/model/reportTypes'
import { fieldOf, reduce, REPORT_CATALOG, uidAt } from '../../../../test/reportDesigner'
import { designKey } from './designKey'
import { fromReportRequest } from './fromRequest'

/** 편집 화면의 "저장 안 됨" 판정 기준: 설계 내용이 같으면 같은 문자열. */

const SAVED: ReportQueryInput = {
  columns: [
    { field: 'deal.vendor', group: true },
    { field: 'deal.amount', group: false, aggregate: 'sum', sort: 'desc' },
  ],
  conditions: [{ field: 'deal.amount', operator: 'gte', value: 1_500_000 }],
  combine: 'and',
  rowLimit: 1000,
}

const load = () => fromReportRequest(SAVED, REPORT_CATALOG, REPORT_CATALOG.limits)
const keyOf = (state: ReturnType<typeof load>) => designKey(state, REPORT_CATALOG)

describe('designKey', () => {
  // 테스트 코드: RS-080
  it('불러온 상태의 키는 같고 고쳤다가 되돌리면 같아진다', () => {
    // given: 저장된 설계를 불러온 상태
    const loaded = load()
    const baseline = keyOf(loaded)

    // when: 컬럼을 넣었다가 뺀다
    const edited = reduce(loaded, { type: 'addColumn', field: fieldOf('deal.code') })
    const editedKey = keyOf(edited)
    const undone = reduce(edited, { type: 'removeColumn', uid: edited.columns[2]?.uid ?? -1 })

    // then: 고치면 키가 달라지고 되돌리면 원래 키다
    expect(typeof baseline).toBe('string')
    expect(keyOf(load())).toBe(baseline)
    expect(editedKey).not.toBe(baseline)
    expect(keyOf(undone)).toBe(baseline)
  })

  it('키는 uid나 선택된 컬럼에 달라지지 않는다', () => {
    // given: 컬럼을 넣었다 빼서 uid 번호가 달라진 상태
    const loaded = load()
    // when: 선택 컬럼만 바꾼다
    const shifted = reduce(loaded, { type: 'addColumn', field: fieldOf('deal.code') })
    const removed = reduce(shifted, { type: 'removeColumn', uid: shifted.columns[2]?.uid ?? -1 })

    // then: 키는 처음과 같다
    expect(removed.nextUid).not.toBe(loaded.nextUid)
    expect(keyOf(reduce(removed, { type: 'selectColumn', uid: uidAt(removed, 0) }))).toBe(keyOf(loaded))
  })

  it.each([
    ['컬럼 라벨', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 1), patch: { label: '합계' } })],
    ['앞 N자 옵션', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 0), patch: { prefixOn: true, prefixLength: 4 } })],
    ['AND/OR 결합', (s: ReturnType<typeof load>) => reduce(s, { type: 'setCombine', combine: 'or' })],
    ['행 수 제한', (s: ReturnType<typeof load>) => reduce(s, { type: 'setRowLimit', rowLimit: 100 })],
    ['컬럼 정렬 방향', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 1), patch: { sort: 'asc' } })],
    ['컬럼 정렬 끄기', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 1), patch: { sort: null } })],
    ['다른 컬럼의 정렬', (s: ReturnType<typeof load>) => reduce(s, { type: 'updateColumn', uid: uidAt(s, 0), patch: { sort: 'asc' } })],
    ['컬럼 순서', (s: ReturnType<typeof load>) => reduce(s, { type: 'moveColumn', uid: uidAt(s, 1), to: 0 })],
    ['조건 값', (s: ReturnType<typeof load>) => reduce(s, { type: 'changeDraft', uid: s.conditions[0]?.uid ?? -1, draft: { shape: 'number', text: '2000' } })],
  ])('설계의 %s이(가) 바뀌면 키가 바뀐다', (_name, edit) => {
    // when: 해당 항목을 편집한 설계의 키를 구한다
    const actual = keyOf(edit(load()))
    // then: 해당 편집 뒤 키가 불러온 상태와 다르다
    expect(actual).not.toBe(keyOf(load()))
  })

  it('조건 값을 읽을 수 없어도 키를 만들고 다른 초안과 구별한다', () => {
    // given: 숫자 조건이 있는 상태
    const loaded = load()
    const uid = loaded.conditions[0]?.uid ?? -1
    // when: 읽을 수 없는 값과 다른 읽을 수 없는 값을 넣는다
    const unreadable = reduce(loaded, { type: 'changeDraft', uid, draft: { shape: 'number', text: 'abc' } })
    const other = reduce(loaded, { type: 'changeDraft', uid, draft: { shape: 'number', text: 'abd' } })

    // then: 키가 서로 다르고 같은 입력이면 같다
    expect(keyOf(unreadable)).not.toBe(keyOf(loaded))
    expect(keyOf(unreadable)).not.toBe(keyOf(other))
    expect(keyOf(unreadable)).toBe(keyOf(reduce(loaded, { type: 'changeDraft', uid, draft: { shape: 'number', text: 'abc' } })))
  })

  // 테스트 코드: RS-080
  it('컬럼 정렬을 되돌리면 같은 키가 된다', () => {
    // given: 불러온 상태
    const loaded = load()
    // when: 정렬을 바꿨다 되돌린다
    const flipped = reduce(loaded, { type: 'updateColumn', uid: uidAt(loaded, 1), patch: { sort: 'asc' } })
    const back = reduce(flipped, { type: 'updateColumn', uid: uidAt(flipped, 1), patch: { sort: 'desc' } })

    // then: 원래 키다
    expect(keyOf(back)).toBe(keyOf(loaded))
  })

  it('어느 컬럼이 정렬을 가졌는지 구별한다', () => {
    // given: 불러온 상태
    const loaded = load()
    // when: 정렬을 다른 컬럼으로 옮긴다
    const moved = reduce(
      loaded,
      { type: 'updateColumn', uid: uidAt(loaded, 1), patch: { sort: null } },
      { type: 'updateColumn', uid: uidAt(loaded, 0), patch: { sort: 'desc' } },
    )

    // then: 키가 달라진다
    expect(keyOf(moved)).not.toBe(keyOf(loaded))
  })
})

describe('designKey와 결과 배치', () => {
  // 테스트 코드: RS-091
  it('배치만 바뀌어도 키가 바뀌고 되돌리면 같아진다', () => {
    // given: 불러온 상태의 키
    const loaded = load()
    const baseline = keyOf(loaded)

    // when: 타일을 옮기거나 보기 방식을 바꾼다
    const sided = reduce(loaded, { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })
    const viewed = reduce(loaded, { type: 'setResultView', view: 'table' })
    const back = reduce(sided, { type: 'placeTile', dragged: 'chart', target: 'table', edge: 'bottom' })

    // then: 키가 달라지고 원래 배치로 돌리면 같다
    expect(keyOf(sided)).not.toBe(baseline)
    expect(keyOf(viewed)).not.toBe(baseline)
    expect(keyOf(sided)).not.toBe(keyOf(viewed))
    expect(keyOf(back)).toBe(baseline)
  })

  // 테스트 코드: RS-091
  it('한 줄 배치가 같아도 순서가 다르면 구별한다', () => {
    // given: 불러온 상태
    const loaded = load()
    // when: 같은 한 줄 배치에서 순서만 다르게 놓는다
    const tableFirst = reduce(loaded, { type: 'placeTile', dragged: 'chart', target: 'table', edge: 'right' })
    const chartFirst = reduce(loaded, { type: 'placeTile', dragged: 'table', target: 'chart', edge: 'right' })

    // then: 키가 다르다
    expect(keyOf(tableFirst)).not.toBe(keyOf(chartFirst))
  })

  // 테스트 코드: RS-091
  it('조건 값을 읽을 수 없어도 키에 배치가 담긴다', () => {
    // given: 읽을 수 없는 조건 값
    const loaded = load()
    const uid = loaded.conditions[0]?.uid ?? -1
    // when: 보기 방식을 바꾼다
    const unreadable = reduce(loaded, { type: 'changeDraft', uid, draft: { shape: 'number', text: 'abc' } })

    // then: 키가 달라진다
    expect(keyOf(reduce(unreadable, { type: 'setResultView', view: 'chart' }))).not.toBe(keyOf(unreadable))
  })
})
