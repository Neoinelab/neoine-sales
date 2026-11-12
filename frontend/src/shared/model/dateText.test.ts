import { describe, expect, it } from 'vitest'
import { dateValueError, finalizeDateText, formatDateTyping, isDateValue, isoToDateText, parseDateText } from './dateText'

describe('formatDateTyping', () => {
  // 테스트 코드: UI-001
  it.each([
    ['2026', '2026'],
    ['20261', '2026.1'],
    ['202611', '2026.11'],
    ['2026112', '2026.11.2'],
    ['20261120', '2026.11.20'],
  ])('숫자만 친 %j는 연·월·일 칸으로 나뉘어 %j로 보인다', (raw, text) => {
    // when: 숫자를 치는 중의 글자를 정리한다
    const shown = formatDateTyping(raw)
    // then: yyyy.mm.dd 모양으로 나뉜다
    expect(shown).toBe(text)
  })

  // 테스트 코드: UI-002
  it.each([
    ['2026-11-20', '2026.11.20'],
    ['2026/11/20', '2026.11.20'],
    ['2026.11.20', '2026.11.20'],
    ['2026.', '2026.'],
    ['2026.1.', '2026.1.'],
    ['2026.1.5', '2026.1.5'],
    [' 2026-11-20', '2026.11.20'],
    ['2026. 11. 20.', '2026.11.20'],
    ['2026-11-20 ', '2026.11.20'],
    ['  2026 / 11 / 20  ', '2026.11.20'],
  ])('구분자가 들어간 %j는 공백·끝 점을 버리고 %j로 정리된다', (raw, text) => {
    // when: 구분자가 있는 글자를 정리한다
    const shown = formatDateTyping(raw)
    // then: 같은 표기로 정리되고, 덜 친 끝 점은 남는다
    expect(shown).toBe(text)
  })

  // 테스트 코드: UI-003
  it.each([
    ['202611201', '2026.11.20'],
    ['2026112099', '2026.11.20'],
    ['2026.123', '2026.12.3'],
    ['2026a11', '2026.11'],
    ['2026..11', '2026.11'],
    ['', ''],
  ])('칸을 넘치거나 잘못된 글자가 섞인 %j는 %j로 정리된다', (raw, text) => {
    // when: 넘치거나 섞인 글자를 정리한다
    const shown = formatDateTyping(raw)
    // then: 넘친 숫자는 다음 칸으로 가거나 버려지고 문자·겹친 구분자는 버려진다
    expect(shown).toBe(text)
  })
})

describe('finalizeDateText', () => {
  // 테스트 코드: UI-005
  it('한 자리 월·일을 두 자리로 채운다', () => {
    // when: 확정한다
    const text = finalizeDateText('2026.1.5')
    // then: 0으로 채워진다
    expect(text).toBe('2026.01.05')
  })

  // 테스트 코드: UI-005
  it('월이 두 자리면 일만 채운다', () => {
    // when: 확정한다
    const text = finalizeDateText('2026.11.5')
    // then: 일만 채워진다
    expect(text).toBe('2026.11.05')
  })

  // 테스트 코드: UI-005
  it.each(['2026.1', '2026', '2026.', '2026.1.', '', '26.1.5'])('다른 모양 %j는 그대로 둔다', (text) => {
    // when: 확정한다
    const result = finalizeDateText(text)
    // then: 바뀌지 않는다
    expect(result).toBe(text)
  })

  // 테스트 코드: UI-005
  it('이미 완성된 글자는 그대로 둔다', () => {
    // when: 확정한다
    const text = finalizeDateText('2026.11.20')
    // then: 그대로다
    expect(text).toBe('2026.11.20')
  })
})

describe('parseDateText', () => {
  // 테스트 코드: UI-006
  it('완성된 날짜를 ISO 값으로 읽는다', () => {
    // when: 판정한다
    const parsed = parseDateText('2026.11.20')
    // then: valid와 ISO 값이다
    expect(parsed).toEqual({ kind: 'valid', iso: '2026-11-20' })
  })

  // 테스트 코드: UI-006
  it('경계 날짜 1900.01.01과 2999.12.31은 올바른 날짜다', () => {
    // when: 경계 날짜를 판정한다
    const first = parseDateText('1900.01.01')
    const last = parseDateText('2999.12.31')
    // then: 둘 다 valid다
    expect(first).toEqual({ kind: 'valid', iso: '1900-01-01' })
    expect(last).toEqual({ kind: 'valid', iso: '2999-12-31' })
  })

  // 테스트 코드: UI-006
  it('윤년의 2월 29일은 올바른 날짜다', () => {
    // when: 판정한다
    const parsed = parseDateText('2024.02.29')
    // then: valid다
    expect(parsed).toEqual({ kind: 'valid', iso: '2024-02-29' })
  })

  // 테스트 코드: UI-006
  it('윤년이 아닌 해의 2월 29일은 없는 날짜다', () => {
    // when: 판정한다
    const parsed = parseDateText('2025.02.29')
    // then: invalid다
    expect(parsed).toEqual({ kind: 'invalid' })
  })

  // 테스트 코드: UI-006
  it('2월 30일과 13월은 없는 날짜다', () => {
    // when: 판정한다
    const feb30 = parseDateText('2026.02.30')
    const month13 = parseDateText('2026.13.01')
    // then: 둘 다 invalid다
    expect(feb30).toEqual({ kind: 'invalid' })
    expect(month13).toEqual({ kind: 'invalid' })
  })

  // 테스트 코드: UI-006
  it('0월과 0일은 없는 날짜다', () => {
    // when: 판정한다
    const month0 = parseDateText('2026.00.10')
    const day0 = parseDateText('2026.10.00')
    // then: 둘 다 invalid다
    expect(month0).toEqual({ kind: 'invalid' })
    expect(day0).toEqual({ kind: 'invalid' })
  })

  // 테스트 코드: UI-006
  it('30일까지 있는 달의 31일은 없는 날짜다', () => {
    // when: 판정한다
    const parsed = parseDateText('2026.04.31')
    // then: invalid다
    expect(parsed).toEqual({ kind: 'invalid' })
  })

  // 테스트 코드: UI-006
  it('1900년 전과 2999년 뒤는 범위 밖이다', () => {
    // when: 범위 밖 날짜를 판정한다
    const before = parseDateText('1899.12.31')
    const after = parseDateText('3000.01.01')
    // then: 둘 다 out_of_range다
    expect(before).toEqual({ kind: 'out_of_range' })
    expect(after).toEqual({ kind: 'out_of_range' })
  })

  // 테스트 코드: UI-006
  it.each(['2026.1', '2026.11.2', '2026', '2026.', '2026.11.', '202'])('덜 친 %j는 incomplete다', (text) => {
    // when: 판정한다
    const parsed = parseDateText(text)
    // then: incomplete다
    expect(parsed).toEqual({ kind: 'incomplete' })
  })

  // 테스트 코드: UI-006
  it('빈 글자와 공백만 있는 글자는 empty다', () => {
    // when: 판정한다
    const blank = parseDateText('')
    const spaces = parseDateText('   ')
    // then: 둘 다 empty다
    expect(blank).toEqual({ kind: 'empty' })
    expect(spaces).toEqual({ kind: 'empty' })
  })

  // 테스트 코드: UI-006
  it('확정해서 채운 글자도 날짜로 읽는다', () => {
    // when: 확정한 글자를 판정한다
    const parsed = parseDateText(finalizeDateText('2026.1.5'))
    // then: valid다
    expect(parsed).toEqual({ kind: 'valid', iso: '2026-01-05' })
  })
})

describe('isoToDateText', () => {
  // 테스트 코드: UI-012
  it('ISO 날짜를 점 표기로 바꾼다', () => {
    // when: 변환한다
    const text = isoToDateText('2026-11-20')
    // then: 점 표기다
    expect(text).toBe('2026.11.20')
  })

  // 테스트 코드: UI-012
  it('빈 값은 빈 값으로 둔다', () => {
    // when: 변환한다
    const text = isoToDateText('')
    // then: 빈 값이다
    expect(text).toBe('')
  })

  // 테스트 코드: UI-012
  it('ISO가 아닌 글자는 그대로 둔다', () => {
    // when: 변환한다
    const dotted = isoToDateText('2026.13.4')
    const word = isoToDateText('abc')
    // then: 그대로다
    expect(dotted).toBe('2026.13.4')
    expect(word).toBe('abc')
  })
})

describe('isDateValue', () => {
  // 테스트 코드: UI-006
  it('범위 안의 실제 ISO 날짜만 참이다', () => {
    // when: 판정한다
    const results = ['2026-11-20', '1900-01-01', '2999-12-31', '2024-02-29'].map(isDateValue)
    // then: 모두 참이다
    expect(results).toEqual([true, true, true, true])
  })

  // 테스트 코드: UI-006
  it.each(['', '2026-13-01', '2025-02-29', '1899-12-31', '3000-01-01', '2026.11.20', '2026-1-5', '2026-11-20 ', 'abc'])(
    '%j는 거짓이다',
    (value) => {
      // when: 판정한다
      const result = isDateValue(value)
      // then: 거짓이다
      expect(result).toBe(false)
    },
  )
})

describe('dateValueError', () => {
  // 테스트 코드: UI-012
  it('빈 값과 올바른 값은 문구가 없다', () => {
    // when: 문구를 구한다
    const empty = dateValueError('')
    const valid = dateValueError('2026-11-20')
    // then: 둘 다 null이다
    expect(empty).toBeNull()
    expect(valid).toBeNull()
  })

  // 테스트 코드: UI-012
  it('덜 친 글자는 yyyymmdd 형식을 안내한다', () => {
    // when: 문구를 구한다
    const short = dateValueError('2026.1')
    const day = dateValueError('2026.11.2')
    // then: 형식 문구다
    expect(short).toBe('날짜를 yyyymmdd 형식으로 입력하세요.')
    expect(day).toBe('날짜를 yyyymmdd 형식으로 입력하세요.')
  })

  // 테스트 코드: UI-012
  it('없는 날짜는 없는 날짜라고 알린다', () => {
    // when: 문구를 구한다
    const dotted = dateValueError('2026.13.04')
    const iso = dateValueError('2026-02-30')
    // then: 없는 날짜 문구다
    expect(dotted).toBe('없는 날짜입니다.')
    expect(iso).toBe('없는 날짜입니다.')
  })

  // 테스트 코드: UI-012
  it('범위 밖 날짜는 허용 범위를 알린다', () => {
    // when: 문구를 구한다
    const dotted = dateValueError('1899.12.31')
    const iso = dateValueError('3000-01-01')
    // then: 범위 문구다
    expect(dotted).toBe('1900.01.01부터 2999.12.31 사이로 입력하세요.')
    expect(iso).toBe('1900.01.01부터 2999.12.31 사이로 입력하세요.')
  })
})
