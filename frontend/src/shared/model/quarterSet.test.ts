import { describe, expect, it } from 'vitest'
import { QUARTERS, effectiveQuarters, monthsOfQuarters, parseQuarterParam, quarterParam, quarterSummary, toggleQuarter } from './quarterSet'

describe('QUARTERS', () => {
  // 분기 목록은 Q1~Q4 순서다.
  it('lists the four quarters in order', () => {
    // when: 분기 목록을 읽는다
    const quarters = QUARTERS

    // then: 1, 2, 3, 4 순서다
    expect(quarters).toEqual([1, 2, 3, 4])
  })
})

describe('parseQuarterParam (URL 분기 값 → 오름차순·중복 제거)', () => {
  // 값이 없거나 빈 문자열이면 분기 없음으로 읽는다.
  it.each([null, ''])('reads %j as no quarter', (raw) => {
    // when: URL 값을 읽는다
    const quarters = parseQuarterParam(raw)

    // then: 빈 목록이다
    expect(quarters).toEqual([])
  })

  // 분기 하나를 읽는다.
  it('reads one quarter', () => {
    // when: '2'를 읽는다
    const quarters = parseQuarterParam('2')

    // then: [2]다
    expect(quarters).toEqual([2])
  })

  // 오름차순으로 정렬하고 중복을 없앤다.
  it('sorts ascending and drops duplicates', () => {
    // when: '3,1,1'을 읽는다
    const quarters = parseQuarterParam('3,1,1')

    // then: [1, 3]이다
    expect(quarters).toEqual([1, 3])
  })

  // 형식이 틀린 항목은 버리고 올바른 항목만 남긴다.
  it('drops items in the wrong format and keeps the valid ones', () => {
    // when: 틀린 항목이 섞인 값을 읽는다
    const quarters = parseQuarterParam(' 1 , 5,x,4')

    // then: 올바른 1, 4만 남는다
    expect(quarters).toEqual([1, 4])
  })

  // 올바른 항목이 하나도 없으면 값 전체를 버린다.
  it.each(['0', '5', '-1', '1.5', 'abc', '01', ',', ' '])('drops the whole value %j when no item is valid', (raw) => {
    // when: 올바른 항목이 없는 값을 읽는다
    const quarters = parseQuarterParam(raw)

    // then: 빈 목록이다
    expect(quarters).toEqual([])
  })

  // 네 분기를 모두 고른 값은 그대로 유지한다(사용자가 누른 상태를 화면에 보인다).
  it('keeps all four quarters as they are (the screen shows what the user pressed)', () => {
    // when: 네 분기를 두 가지 순서로 읽는다
    const ascending = parseQuarterParam('1,2,3,4')
    const descending = parseQuarterParam('4,3,2,1')

    // then: 둘 다 [1, 2, 3, 4]다
    expect(ascending).toEqual([1, 2, 3, 4])
    expect(descending).toEqual([1, 2, 3, 4])
  })
})

describe('quarterParam', () => {
  // 오름차순 쉼표 목록으로 쓴다.
  it('writes an ascending comma list', () => {
    // when: [3, 1]을 URL 값으로 쓴다
    const text = quarterParam([3, 1])

    // then: '1,3'이다
    expect(text).toBe('1,3')
  })

  // 분기가 없으면 빈 문자열이다.
  it('writes an empty string for no quarter', () => {
    // when: 빈 목록을 쓴다
    const text = quarterParam([])

    // then: 빈 문자열이다
    expect(text).toBe('')
  })

  // 중복은 한 번만 쓴다.
  it('drops duplicates', () => {
    // when: 중복이 있는 목록을 쓴다
    const text = quarterParam([2, 2, 4])

    // then: '2,4'다
    expect(text).toBe('2,4')
  })

  // 네 분기를 모두 고르면 그대로 쓴다.
  it('writes all four quarters as they are', () => {
    // when: 네 분기를 거꾸로 쓴다
    const text = quarterParam([4, 3, 2, 1])

    // then: '1,2,3,4'다
    expect(text).toBe('1,2,3,4')
  })
})

describe('toggleQuarter', () => {
  // 분기를 켜면 오름차순을 유지한다.
  it('turns a quarter on and keeps the list ascending', () => {
    // when: 1분기만 있는 목록에 3분기를, 3분기만 있는 목록에 1분기를 켠다
    const addedAfter = toggleQuarter([1], 3, true)
    const addedBefore = toggleQuarter([3], 1, true)

    // then: 둘 다 [1, 3]이다
    expect(addedAfter).toEqual([1, 3])
    expect(addedBefore).toEqual([1, 3])
  })

  // 분기를 끈다.
  it('turns a quarter off', () => {
    // when: [1, 3]에서 1분기를 끈다
    const result = toggleQuarter([1, 3], 1, false)

    // then: [3]이다
    expect(result).toEqual([3])
  })

  // 마지막 분기도 끌 수 있어 아무것도 남지 않는다.
  it('can turn the last quarter off, leaving none', () => {
    // when: [2]에서 2분기를 끈다
    const result = toggleQuarter([2], 2, false)

    // then: 빈 목록이다
    expect(result).toEqual([])
  })

  // 이미 켜진 분기를 다시 켜도 그대로다.
  it('does not change anything when a quarter that is on is turned on again', () => {
    // when: [1, 3]에서 3분기를 다시 켠다
    const result = toggleQuarter([1, 3], 3, true)

    // then: [1, 3]이다
    expect(result).toEqual([1, 3])
  })

  // 이미 꺼진 분기를 다시 꺼도 그대로다.
  it('does not change anything when a quarter that is off is turned off again', () => {
    // when: [1, 3]에서 2분기를 끈다
    const result = toggleQuarter([1, 3], 2, false)

    // then: [1, 3]이다
    expect(result).toEqual([1, 3])
  })

  // 받은 목록을 바꾸지 않는다.
  it('does not mutate the list it is given', () => {
    // given: 1분기만 있는 목록
    const quarters = [1] as const

    // when: 2분기를 켠다
    toggleQuarter(quarters, 2, true)

    // then: 원래 목록은 그대로다
    expect(quarters).toEqual([1])
  })

  // 네 번째를 켜면 넷이 모두 남는다(여기서는 정규화하지 않는다).
  it('keeps all four when the fourth is turned on (no normalization here)', () => {
    // when: [1, 2, 3]에서 4분기를 켠다
    const result = toggleQuarter([1, 2, 3], 4, true)

    // then: [1, 2, 3, 4]다
    expect(result).toEqual([1, 2, 3, 4])
  })
})

describe('effectiveQuarters (조회·Drill-down용: 없음 = 넷 다 = 전체)', () => {
  // 분기가 없으면 조건이 없다.
  it('treats no quarter as no condition', () => {
    // when: 빈 목록의 유효 분기를 구한다
    const result = effectiveQuarters([])

    // then: 빈 목록이다
    expect(result).toEqual([])
  })

  // 넷 다 고르면 조건이 없다.
  it('treats all four quarters as no condition', () => {
    // when: 네 분기를 두 가지 순서로 구한다
    const ascending = effectiveQuarters([1, 2, 3, 4])
    const descending = effectiveQuarters([4, 3, 2, 1])

    // then: 둘 다 빈 목록이다
    expect(ascending).toEqual([])
    expect(descending).toEqual([])
  })

  // 한 개~세 개는 오름차순으로 유지한다.
  it('keeps one to three quarters ascending', () => {
    // when: 한 개~세 개를 구한다
    const two = effectiveQuarters([3, 1])
    const one = effectiveQuarters([2])
    const three = effectiveQuarters([1, 2, 4])

    // then: 오름차순으로 그대로다
    expect(two).toEqual([1, 3])
    expect(one).toEqual([2])
    expect(three).toEqual([1, 2, 4])
  })
})

describe('quarterSummary', () => {
  // 없거나 넷 다면 '전체'라고 한다.
  it('says 전체 for no quarter and for all four', () => {
    // when: 빈 목록과 네 분기의 요약을 구한다
    const none = quarterSummary([])
    const all = quarterSummary([1, 2, 3, 4])

    // then: 둘 다 '전체'다
    expect(none).toBe('전체')
    expect(all).toBe('전체')
  })

  // 고른 분기를 오름차순으로 나열한다.
  it('lists the chosen quarters ascending', () => {
    // when: 두 개와 한 개의 요약을 구한다
    const two = quarterSummary([3, 1])
    const one = quarterSummary([4])

    // then: 'Q1, Q3'와 'Q4'다
    expect(two).toBe('Q1, Q3')
    expect(one).toBe('Q4')
  })
})

describe('monthsOfQuarters (월 선택지)', () => {
  // 분기가 없거나 넷 다면 열두 달을 보인다.
  it('offers the twelve months for no quarter and for all four', () => {
    // when: 빈 목록과 네 분기의 월을 구한다
    const none = monthsOfQuarters([])
    const all = monthsOfQuarters([1, 2, 3, 4])

    // then: 둘 다 1~12월이다
    expect(none).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
    expect(all).toEqual([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])
  })

  // 고른 분기들의 월을 합쳐 오름차순으로 보인다.
  it('offers the union of the months of the chosen quarters ascending', () => {
    // when: 1·3분기를 두 가지 순서로 구한다
    const ascending = monthsOfQuarters([1, 3])
    const descending = monthsOfQuarters([3, 1])

    // then: 둘 다 1~3월, 7~9월이다
    expect(ascending).toEqual([1, 2, 3, 7, 8, 9])
    expect(descending).toEqual([1, 2, 3, 7, 8, 9])
  })

  // 한 분기면 그 분기의 세 달이다.
  it('offers the three months of one quarter', () => {
    // when: 4분기의 월을 구한다
    const months = monthsOfQuarters([4])

    // then: 10~12월이다
    expect(months).toEqual([10, 11, 12])
  })
})
