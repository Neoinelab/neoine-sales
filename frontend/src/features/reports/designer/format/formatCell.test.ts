import { describe, expect, it } from 'vitest'
import { resultColumn } from '../../../../test/reportDesigner'
import { cellTitle, columnHeader, formatCell, formatShownCell, isThousandWonColumn, truncateLabel } from './formatCell'

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27' }

/** 금액 열: 서버가 unit 'krw_thousand'를 준다(format은 항상 null). */
const amount = (over: object = {}) =>
  resultColumn({ field: 'deal.amount', type: 'number', valueType: 'integer', format: null, unit: 'krw_thousand', aggregate: 'sum', ...over })

/** 금액이 아닌 숫자 열(Users count 등): unit 없음. */
const plain = (over: object = {}) =>
  resultColumn({ field: 'deal.users', type: 'number', valueType: 'integer', format: null, unit: null, aggregate: 'sum', ...over })

describe('formatCell amount in thousand won (AC-6)', () => {
  it.each([
    ['sum', 123_456_789, 'integer', '123,457'],
    ['sum', 1_234_499, 'integer', '1,234'],
    ['sum', 1_234_500, 'integer', '1,235'],
    ['avg', 1499.5, 'decimal', '2'],
    ['avg', 1234.4, 'decimal', '1'],
    ['min', 500, 'integer', '1'],
    ['max', 499, 'integer', '0'],
    ['sum', 0, 'integer', '0'],
    ['sum', 3_456_000_000, 'integer', '3,456,000'],
  ] as const)('rounds %s %s won to thousand won: %s', (aggregate, value, valueType, expected) => {
    expect(formatCell(value, amount({ aggregate, valueType }), CTX)).toBe(expected)
  })

  it('shows a count aggregate of an amount-unit column as a plain count', () => {
    expect(formatCell(1_234_567, amount({ aggregate: 'count' }), CTX)).toBe('1,234,567')
  })

  it('shows the amount column of a plain row (no aggregate) in thousand won too', () => {
    expect(formatCell(5_000_000, amount({ aggregate: null }), CTX)).toBe('5,000')
  })
})

describe('formatCell other numbers (AC-7)', () => {
  it.each([
    [1234, 'integer', 'sum', '1,234'],
    [0, 'integer', 'sum', '0'],
    [2.5, 'decimal', 'avg', '3'],
    [12.49, 'decimal', 'avg', '12'],
    [1234.5, 'decimal', 'avg', '1,235'],
    [1_234_567, 'integer', 'count', '1,234,567'],
  ] as const)('shows %s as a whole number with separators: %s', (value, valueType, aggregate, expected) => {
    expect(formatCell(value, plain({ valueType, aggregate }), CTX)).toBe(expected)
  })

  it('does not separate a year bucket', () => {
    const year = resultColumn({ type: 'date', valueType: 'integer', format: 'year' })

    expect(formatCell(2026, year, CTX)).toBe('2026')
  })

  it('does not divide an amount-unit year bucket either', () => {
    expect(formatCell(2026, amount({ format: 'year', aggregate: null }), CTX)).toBe('2026')
  })

  it('shows a dash for an empty cell in every kind of column', () => {
    expect(formatCell(null, amount(), CTX)).toBe('—')
    expect(formatCell(null, plain(), CTX)).toBe('—')
    expect(formatCell(null, resultColumn(), CTX)).toBe('—')
    expect(formatCell(null, resultColumn({ type: 'date', valueType: 'date', format: 'ymd' }), CTX)).toBe('—')
  })

  it('separates the thousands of a count on a text column', () => {
    const column = resultColumn({ valueType: 'integer', aggregate: 'count' })

    expect(formatCell(12_345, column, CTX)).toBe('12,345')
    expect(formatCell(0, resultColumn({ valueType: 'integer', aggregate: 'count_distinct' }), CTX)).toBe('0')
  })
})

describe('isThousandWonColumn (AC-6)', () => {
  it('is true only for an amount-unit column that is not a count', () => {
    expect(isThousandWonColumn(amount())).toBe(true)
    expect(isThousandWonColumn(amount({ aggregate: null }))).toBe(true)
    expect(isThousandWonColumn(amount({ aggregate: 'count' }))).toBe(false)
    expect(isThousandWonColumn(amount({ aggregate: 'count_distinct' }))).toBe(false)
    expect(isThousandWonColumn(plain())).toBe(false)
  })
})

describe('formatCell text (AC12)', () => {
  it('shows text, codes and users as they are', () => {
    expect(formatCell('한빛은행 도입', resultColumn(), CTX)).toBe('한빛은행 도입')
    expect(formatCell('기회발굴', resultColumn({ type: 'code', format: null }), CTX)).toBe('기회발굴')
    expect(formatCell('김영업', resultColumn({ type: 'user', format: null }), CTX)).toBe('김영업')
  })

  it('does not cut a value even when the column has a prefix length', () => {
    expect(formatCell('abcdefghij', resultColumn({ prefixLength: 3 }), CTX)).toBe('abcdefghij')
    expect(formatCell(1_234_567, plain({ prefixLength: 3 }), CTX)).toBe('1,234,567')
  })
})

describe('truncateLabel (AC16)', () => {
  it.each([
    ['ABCDEF', 3, 'ABC…'],
    ['ABC', 3, 'ABC'],
    ['AB', 3, 'AB'],
    ['가나다라마', 2, '가나…'],
    ['😀😀😀😀', 2, '😀😀…'],
    ['😀😀', 2, '😀😀'],
  ])('cuts %s at %i characters by code point', (text, n, expected) => {
    expect(truncateLabel(text, n)).toBe(expected)
  })

  it('keeps the text when there is no prefix length', () => {
    expect(truncateLabel('ABCDEF', null)).toBe('ABCDEF')
  })
})

describe('formatShownCell (AC16)', () => {
  it('cuts a text cell and adds an ellipsis only above the limit', () => {
    const column = resultColumn({ prefixLength: 3 })

    expect(formatShownCell('ABCDEF', column, CTX)).toBe('ABC…')
    expect(formatShownCell('ABC', column, CTX)).toBe('ABC')
  })

  it('cuts the formatted string of a number', () => {
    expect(formatShownCell(1_234_567, plain({ prefixLength: 3 }), CTX)).toBe('1,2…')
  })

  it('cuts the formatted string of a date', () => {
    const column = resultColumn({ field: 'deal.expected_close', type: 'date', valueType: 'date', format: 'weekday', prefixLength: 4 })

    expect(formatShownCell('2026-10-27', column, CTX)).toBe('2026…')
  })

  it('never cuts an empty value dash', () => {
    expect(formatShownCell(null, resultColumn({ prefixLength: 1 }), CTX)).toBe('—')
  })

  it('shows the whole formatted value without a prefix length', () => {
    expect(formatShownCell(1_234_567, plain(), CTX)).toBe('1,234,567')
    expect(formatShownCell('ABCDEF', resultColumn(), CTX)).toBe('ABCDEF')
  })
})

describe('cellTitle (AC17)', () => {
  it('gives the whole formatted value when the cell is cut, whatever the type', () => {
    expect(cellTitle(1_234_567, plain({ prefixLength: 3 }), CTX)).toBe('1,234,567')
    expect(cellTitle('ABCDEF', resultColumn({ prefixLength: 3 }), CTX)).toBe('ABCDEF')
  })

  it('gives the text of a text cell that is not cut', () => {
    expect(cellTitle('긴 문장입니다', resultColumn(), CTX)).toBe('긴 문장입니다')
    expect(cellTitle('ABC', resultColumn({ prefixLength: 3 }), CTX)).toBe('ABC')
  })

  it('gives nothing for an empty cell or a number that is not cut', () => {
    expect(cellTitle(null, resultColumn(), CTX)).toBeUndefined()
    expect(cellTitle(1234, plain(), CTX)).toBeUndefined()
    expect(cellTitle(12, plain({ prefixLength: 5 }), CTX)).toBeUndefined()
  })
})

describe('formatCell dates and times (AC12, AC17)', () => {
  const date = (format: string) => resultColumn({ field: 'deal.expected_close', type: 'date', valueType: 'date', format: format as never })
  const stamp = (format: string, valueType: 'datetime' | 'date' = 'datetime') =>
    resultColumn({ field: 'deal.created_at', type: 'datetime', valueType, format: format as never })

  it('formats dates and times with the server offset and app clock', () => {
    expect(formatCell('2026-10-27', date('ymd'), CTX)).toBe('2026-10-27')
    expect(formatCell('2026-10-27', date('weekday'), CTX)).toBe('2026-10-27 (화)')
    expect(formatCell('2026-10-24', date('relative'), CTX)).toBe('3일 전')
    expect(formatCell('2026-10-27', date('relative'), CTX)).toBe('오늘')
    expect(formatCell('2026-10-30', date('relative'), CTX)).toBe('3일 후')
    expect(formatCell('2026-04-01T00:30:00+09:00', stamp('ymd_hm'), CTX)).toBe('2026-04-01 00:30')
    expect(formatCell('2026-04-01T00:30:00+09:00', stamp('weekday'), CTX)).toBe('2026-04-01 (수)')
    expect(formatCell('2026-10-27T08:00:00+09:00', stamp('relative'), CTX)).toBe('1시간 전')
  })

  it('shows the wall clock of the offset the server wrote, not the browser zone', () => {
    expect(formatCell('2026-03-31T23:45:00-05:00', stamp('ymd_hm'), CTX)).toBe('2026-03-31 23:45')
  })

  it('shows server buckets as they are', () => {
    expect(formatCell(2026, resultColumn({ type: 'date', valueType: 'integer', format: 'year' }), CTX)).toBe('2026')
    expect(formatCell('2026 Q4', resultColumn({ type: 'date', valueType: 'text', format: 'quarter' }), CTX)).toBe('2026 Q4')
    expect(formatCell('2026-10', resultColumn({ type: 'datetime', valueType: 'text', format: 'month' }), CTX)).toBe('2026-10')
    expect(formatCell('2026-10-27', stamp('ymd', 'date'), CTX)).toBe('2026-10-27')
  })
})

describe('columnHeader (AC-6)', () => {
  it('adds the thousand won unit to the header of an amount column', () => {
    expect(columnHeader(amount({ label: '금액 합계' }))).toMatch(/^금액 합계\s?\(천원\)$/)
    expect(columnHeader(amount({ label: '금액 평균', aggregate: 'avg' }))).toMatch(/^금액 평균\s?\(천원\)$/)
  })

  it('has no unit when the amount column is only counted', () => {
    expect(columnHeader(amount({ label: '건수', aggregate: 'count' }))).toBe('건수')
  })

  it('keeps the label of every other column', () => {
    expect(columnHeader(plain({ label: 'Users count 합계' }))).toBe('Users count 합계')
    expect(columnHeader(resultColumn({ label: 'Deal code' }))).toBe('Deal code')
  })
})
