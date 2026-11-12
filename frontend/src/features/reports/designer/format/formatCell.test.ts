import { describe, expect, it } from 'vitest'
import { resultColumn } from '../../../../test/reportDesigner'
import { cellTitle, columnHeader, formatCell, formatShownCell, isWonColumn, truncateLabel } from './formatCell'

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }

/** 금액 열: 서버가 unit 'krw'를 준다(format은 항상 null). */
const amount = (over: object = {}) =>
  resultColumn({ field: 'deal.amount', type: 'number', valueType: 'integer', format: null, unit: 'krw', aggregate: 'sum', ...over })

/** 금액이 아닌 숫자 열(Users count 등): unit 없음. */
const plain = (over: object = {}) =>
  resultColumn({ field: 'deal.users', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum', ...over })

describe('formatCell amount in won', () => {
  // 테스트 코드: RQ-096
  it.each([
    ['sum', 123_456_789, 'integer', '123,456,789'],
    ['sum', 1_234_499, 'integer', '1,234,499'],
    ['sum', 1_234_500, 'integer', '1,234,500'],
    ['avg', 1_234_567.6, 'decimal', '1,234,568'],
    ['avg', 1499.5, 'decimal', '1,500'],
    ['avg', 1234.4, 'decimal', '1,234'],
    ['min', 500, 'integer', '500'],
    ['max', 499, 'integer', '499'],
    ['sum', 0, 'integer', '0'],
    ['sum', 3_456_000_000, 'integer', '3,456,000,000'],
  ] as const)('금액 열의 %s %s원은 천 단위 구분 정수로 보인다: %s', (aggregate, value, valueType, expected) => {
    // when: 집계·값 종류 사례별로 금액 열의 값을 서식한다
    const actual = formatCell(value, amount({ aggregate, valueType }), CTX)
    // then: 집계와 값에 따라 소수 없는 반올림 값이 콤마 정수로 보인다
    expect(actual).toBe(expected)
  })

  // 테스트 코드: RQ-096
  it('금액 열의 건수 집계는 그냥 건수로 보인다', () => {
    // when: 금액 열에서 건수 집계 값 1,234,567을 서식한다
    const actual = formatCell(1_234_567, amount({ aggregate: 'count' }), CTX)
    // then: 콤마 정수 건수다
    expect(actual).toBe('1,234,567')
  })

  // 테스트 코드: RQ-096
  it('집계 없는 일반 행의 금액도 원으로 보인다', () => {
    // when: 집계 없는 금액 열에서 5,000,000을 서식한다
    const actual = formatCell(5_000_000, amount({ aggregate: null }), CTX)
    // then: 콤마 정수 원이다
    expect(actual).toBe('5,000,000')
  })
})

describe('formatCell other numbers', () => {
  // 테스트 코드: RQ-096
  it.each([
    [1234, 'integer', 'sum', '1,234'],
    [0, 'integer', 'sum', '0'],
    [2.5, 'decimal', 'avg', '3'],
    [12.49, 'decimal', 'avg', '12'],
    [1234.5, 'decimal', 'avg', '1,235'],
    [1_234_567, 'integer', 'count', '1,234,567'],
  ] as const)('%s은 천 단위 구분 정수로 보인다: %s', (value, valueType, aggregate, expected) => {
    // when: 값·값 종류·집계 사례별로 일반 숫자 열의 값을 서식한다
    const actual = formatCell(value, plain({ valueType, aggregate }), CTX)
    // then: 소수는 반올림한 콤마 정수다
    expect(actual).toBe(expected)
  })

  // 테스트 코드: RQ-096
  it('연도 묶음 값에는 천 단위 구분을 넣지 않는다', () => {
    // given: 연도 묶음 열
    const year = resultColumn({ type: 'date', valueType: 'integer', format: 'year' })

    // when: 연도 묶음 열에서 2026을 서식한다
    const actual = formatCell(2026, year, CTX)
    // then: 2026 그대로다
    expect(actual).toBe('2026')
  })

  // 테스트 코드: RQ-096
  it('금액 단위 열의 연도 묶음도 천 단위 구분을 넣지 않는다', () => {
    // when: 연도 묶음 금액 열에서 2026을 서식한다
    const actual = formatCell(2026, amount({ format: 'year', aggregate: null }), CTX)
    // then: 2026 그대로다
    expect(actual).toBe('2026')
  })

  // 테스트 코드: RQ-096
  it('빈 칸은 어떤 열에서든 —로 보인다', () => {
    // when: 금액 열과 일반 열에서 null 값을 서식한다
    const actual = formatCell(null, amount(), CTX)
    const actual2 = formatCell(null, plain(), CTX)
    const actual3 = formatCell(null, resultColumn(), CTX)
    const actual4 = formatCell(null, resultColumn({ type: 'date', valueType: 'date', format: 'ymd' }), CTX)
    // then: 금액·숫자·텍스트·날짜 열 모두 —다
    expect(actual).toBe('—')
    expect(actual2).toBe('—')
    expect(actual3).toBe('—')
    expect(actual4).toBe('—')
  })

  // 테스트 코드: RQ-096
  it('텍스트 열의 건수도 천 단위를 구분한다', () => {
    // given: 건수 집계 텍스트 열
    const column = resultColumn({ valueType: 'integer', aggregate: 'count' })

    // when: 건수·고유 건수 집계 열에서 12,345와 0을 서식한다
    const actual = formatCell(12_345, column, CTX)
    const actual2 = formatCell(0, resultColumn({ valueType: 'integer', aggregate: 'count_distinct' }), CTX)
    // then: 12,345와 0이다
    expect(actual).toBe('12,345')
    expect(actual2).toBe('0')
  })
})

describe('isWonColumn', () => {
  // 테스트 코드: RQ-096
  it('원 열은 단위가 금액이고 건수 집계가 아닐 때만 true다', () => {
    // when: 금액 열, 집계 없는 금액 열 등을 원 열인지 판정한다
    const actual = isWonColumn(amount())
    const actual2 = isWonColumn(amount({ aggregate: null }))
    const actual3 = isWonColumn(amount({ aggregate: 'count' }))
    const actual4 = isWonColumn(amount({ aggregate: 'count_distinct' }))
    const actual5 = isWonColumn(plain())
    // then: 금액 열은 true, 건수·고유 건수 집계와 일반 숫자 열은 false다
    expect(actual).toBe(true)
    expect(actual2).toBe(true)
    expect(actual3).toBe(false)
    expect(actual4).toBe(false)
    expect(actual5).toBe(false)
  })
})

describe('formatCell text', () => {
  // 테스트 코드: RQ-096
  it('텍스트·코드·사용자 값은 그대로 보인다', () => {
    // when: 텍스트 값과 코드 값 "기회발굴"을 서식한다
    const actual = formatCell('한빛은행 도입', resultColumn(), CTX)
    const actual2 = formatCell('기회발굴', resultColumn({ type: 'code', format: null }), CTX)
    const actual3 = formatCell('김영업', resultColumn({ type: 'user', format: null }), CTX)
    // then: 값이 그대로 보인다
    expect(actual).toBe('한빛은행 도입')
    expect(actual2).toBe('기회발굴')
    expect(actual3).toBe('김영업')
  })

  // 테스트 코드: RQ-098
  it('앞 N자가 있어도 formatCell은 값을 자르지 않는다', () => {
    // when: 앞 N자 3인 텍스트 열과 숫자 열의 값을 서식한다
    const actual = formatCell('abcdefghij', resultColumn({ prefixLength: 3 }), CTX)
    const actual2 = formatCell(1_234_567, plain({ prefixLength: 3 }), CTX)
    // then: 전체 값이 그대로다 (자르기는 formatShownCell의 몫)
    expect(actual).toBe('abcdefghij')
    expect(actual2).toBe('1,234,567')
  })
})

describe('truncateLabel', () => {
  // 테스트 코드: RQ-098
  it.each([
    ['ABCDEF', 3, 'ABC…'],
    ['ABC', 3, 'ABC'],
    ['AB', 3, 'AB'],
    ['가나다라마', 2, '가나…'],
    ['😀😀😀😀', 2, '😀😀…'],
    ['😀😀', 2, '😀😀'],
  ])('%s을 %i자에서 코드 포인트 기준으로 자른다', (text, n, expected) => {
    // when: 글자 수를 넘는다 (전제: 문자열·길이 매개변수)
    const actual = truncateLabel(text, n)
    // then: …를 붙여 자르고 이모지도 한 글자로 센다
    expect(actual).toBe(expected)
  })

  // 테스트 코드: RQ-098
  it('앞 N자가 없으면 글을 그대로 둔다', () => {
    // when: 앞 N자 없이 "ABCDEF"를 자른다
    const actual = truncateLabel('ABCDEF', null)
    // then: 전체 값이다
    expect(actual).toBe('ABCDEF')
  })
})

describe('formatShownCell', () => {
  // 테스트 코드: RQ-098
  it('텍스트 칸은 한도를 넘을 때만 자르고 …를 붙인다', () => {
    // given: 앞 N자 3 열
    const column = resultColumn({ prefixLength: 3 })

    // when: 넘는다
    const actual = formatShownCell('ABCDEF', column, CTX)
    const actual2 = formatShownCell('ABC', column, CTX)
    // then: ABC…, 같으면 ABC다
    expect(actual).toBe('ABC…')
    expect(actual2).toBe('ABC')
  })

  // 테스트 코드: RQ-098
  it('숫자는 서식을 입힌 문자열을 자른다', () => {
    // when: 앞 N자 3인 숫자 열에서 1,234,567의 표시 값을 구한다
    const actual = formatShownCell(1_234_567, plain({ prefixLength: 3 }), CTX)
    // then: 1,2…다
    expect(actual).toBe('1,2…')
  })

  // 테스트 코드: RQ-098
  it('날짜는 서식을 입힌 문자열을 자른다', () => {
    // given: 요일 포맷과 앞 N자 4인 날짜 열
    const column = resultColumn({ field: 'deal.expected_close', type: 'date', valueType: 'date', format: 'weekday', prefixLength: 4 })

    // when: 앞 N자 4인 요일 포맷 날짜 열에서 2026-10-27의 표시 값을 구한다
    const actual = formatShownCell('2026-10-27', column, CTX)
    // then: 2026…다
    expect(actual).toBe('2026…')
  })

  // 테스트 코드: RQ-098
  it('빈 값 대시는 자르지 않는다', () => {
    // when: 앞 N자 1인 열에서 null의 표시 값을 구한다
    const actual = formatShownCell(null, resultColumn({ prefixLength: 1 }), CTX)
    // then: —다
    expect(actual).toBe('—')
  })

  // 테스트 코드: RQ-098
  it('앞 N자가 없으면 서식을 입힌 값 전체를 보인다', () => {
    // when: 앞 N자 없는 열에서 숫자와 텍스트의 표시 값을 구한다
    const actual = formatShownCell(1_234_567, plain(), CTX)
    const actual2 = formatShownCell('ABCDEF', resultColumn(), CTX)
    // then: 1,234,567과 ABCDEF 전체다
    expect(actual).toBe('1,234,567')
    expect(actual2).toBe('ABCDEF')
  })
})

describe('cellTitle', () => {
  // 테스트 코드: RQ-098
  it('잘린 칸의 title은 형식과 상관없이 서식을 입힌 전체 값이다', () => {
    // when: 앞 N자 3인 열에서 숫자와 텍스트의 title을 구한다
    const actual = cellTitle(1_234_567, plain({ prefixLength: 3 }), CTX)
    const actual2 = cellTitle('ABCDEF', resultColumn({ prefixLength: 3 }), CTX)
    // then: 1,234,567과 ABCDEF다
    expect(actual).toBe('1,234,567')
    expect(actual2).toBe('ABCDEF')
  })

  // 테스트 코드: RQ-098
  it('잘리지 않은 텍스트 칸의 title은 그 텍스트다', () => {
    // when: 긴 문장과 앞 N자 안에 들어오는 "ABC"의 title을 구한다
    const actual = cellTitle('긴 문장입니다', resultColumn(), CTX)
    const actual2 = cellTitle('ABC', resultColumn({ prefixLength: 3 }), CTX)
    // then: 텍스트 그대로다
    expect(actual).toBe('긴 문장입니다')
    expect(actual2).toBe('ABC')
  })

  // 테스트 코드: RQ-098
  it('빈 칸이나 잘리지 않은 숫자는 title이 없다', () => {
    // when: null과 잘리지 않은 숫자 1234의 title을 구한다
    const actual = cellTitle(null, resultColumn(), CTX)
    const actual2 = cellTitle(1234, plain(), CTX)
    const actual3 = cellTitle(12, plain({ prefixLength: 5 }), CTX)
    // then: undefined다
    expect(actual).toBeUndefined()
    expect(actual2).toBeUndefined()
    expect(actual3).toBeUndefined()
  })
})

describe('formatCell dates and times', () => {
  const date = (format: string) => resultColumn({ field: 'deal.expected_close', type: 'date', valueType: 'date', format: format as never })
  const stamp = (format: string, valueType: 'datetime' | 'date' = 'datetime') =>
    resultColumn({ field: 'deal.created_at', type: 'datetime', valueType, format: format as never })

  // 테스트 코드: RQ-097
  it('날짜와 시각을 서버 오프셋과 앱 시계로 서식한다', () => {
    // when: 앱 시계 2026-10-27 09:00 기준으로 날짜 포맷별 값을 서식한다
    const actual = formatCell('2026-10-27', date('ymd'), CTX)
    const actual2 = formatCell('2026-10-27', date('weekday'), CTX)
    const actual3 = formatCell('2026-10-24', date('relative'), CTX)
    const actual4 = formatCell('2026-10-27', date('relative'), CTX)
    const actual5 = formatCell('2026-10-30', date('relative'), CTX)
    const actual6 = formatCell('2026-04-01T00:30:00+09:00', stamp('ymd_hm'), CTX)
    const actual7 = formatCell('2026-04-01T00:30:00+09:00', stamp('weekday'), CTX)
    const actual8 = formatCell('2026-10-27T08:00:00+09:00', stamp('relative'), CTX)
    // then: 연-월-일, 요일, 상대(일 전·오늘·일 후), 연-월-일 시:분, 상대 시각이 기대대로다
    expect(actual).toBe('2026-10-27')
    expect(actual2).toBe('2026-10-27 (화)')
    expect(actual3).toBe('3일 전')
    expect(actual4).toBe('오늘')
    expect(actual5).toBe('3일 후')
    expect(actual6).toBe('2026-04-01 00:30')
    expect(actual7).toBe('2026-04-01 (수)')
    expect(actual8).toBe('1시간 전')
  })

  // 테스트 코드: RQ-097
  it('브라우저 시간대가 아니라 서버가 쓴 오프셋의 벽시계를 보인다', () => {
    // when: -05:00 오프셋 시각 2026-03-31T23:45:00을 서식한다
    const actual = formatCell('2026-03-31T23:45:00-05:00', stamp('ymd_hm'), CTX)
    // then: 오프셋 그대로 23:45로 보인다
    expect(actual).toBe('2026-03-31 23:45')
  })

  // 테스트 코드: RQ-097
  it('서버가 만든 묶음 값은 그대로 보인다', () => {
    // when: 서버가 묶은 연도 2026과 분기 "2026 Q4" 값을 서식한다
    const actual = formatCell(2026, resultColumn({ type: 'date', valueType: 'integer', format: 'year' }), CTX)
    const actual2 = formatCell('2026 Q4', resultColumn({ type: 'date', valueType: 'text', format: 'quarter' }), CTX)
    const actual3 = formatCell('2026-10', resultColumn({ type: 'datetime', valueType: 'text', format: 'month' }), CTX)
    const actual4 = formatCell('2026-10-27', stamp('ymd', 'date'), CTX)
    // then: 연도·분기·월·날짜 묶음 값이 그대로다
    expect(actual).toBe('2026')
    expect(actual2).toBe('2026 Q4')
    expect(actual3).toBe('2026-10')
    expect(actual4).toBe('2026-10-27')
  })
})

describe('columnHeader', () => {
  // 테스트 코드: RQ-096
  it('금액 열 머리글에는 (원) 단위가 붙는다', () => {
    // when: 금액 합계·평균 열의 머리글을 구한다
    const actual = columnHeader(amount({ label: '금액 합계' }))
    const actual2 = columnHeader(amount({ label: '금액 평균', aggregate: 'avg' }))
    // then: 합계와 평균 모두 이름 (원)이다
    expect(actual).toMatch(/^금액 합계\s?\(원\)$/)
    expect(actual2).toMatch(/^금액 평균\s?\(원\)$/)
  })

  // 테스트 코드: RQ-096
  it('금액 열이 건수만 센 것이면 단위가 없다', () => {
    // when: 건수·고유 건수 집계 금액 열의 머리글을 구한다
    const actual = columnHeader(amount({ label: '건수', aggregate: 'count' }))
    const actual2 = columnHeader(amount({ label: '고유 건수', aggregate: 'count_distinct' }))
    // then: 건수와 고유 건수 머리글이 이름 그대로다
    expect(actual).toBe('건수')
    expect(actual2).toBe('고유 건수')
  })

  // 테스트 코드: RQ-096
  it('다른 열은 머리글이 이름 그대로다', () => {
    // when: 일반 열과 코드 열의 머리글을 구한다
    const actual = columnHeader(plain({ label: 'Users count 합계' }))
    const actual2 = columnHeader(resultColumn({ label: 'Deal code' }))
    // then: 단위가 붙지 않는다
    expect(actual).toBe('Users count 합계')
    expect(actual2).toBe('Deal code')
  })
})
