import { describe, expect, it } from 'vitest'
import { resultColumn } from '../../../../test/reportDesigner'
import { cellTitle, columnHeader, formatCell, formatShownCell, truncateLabel } from './formatCell'

const CTX = { now: '2026-10-27T09:00:00+09:00', today: '2026-10-27', totals: null }

const number = (format: string, over: object = {}) =>
  resultColumn({ field: 'deal.amount', type: 'number', valueType: 'integer', format: format as never, ...over })

describe('formatCell numbers (AC12)', () => {
  it.each([
    ['thousands', 1_234_567, 'integer', '1,234,567'],
    ['thousands', 1234.567, 'decimal', '1,234.57'],
    ['thousands', 1234.5, 'decimal', '1,234.5'],
    ['krw_thousand', 1_234_500, 'integer', '1,235'],
    ['krw_thousand', 1_234_499, 'integer', '1,234'],
    ['krw_thousand', 1_234_500.4, 'decimal', '1,235'],
    ['krw_million', 1_500_000, 'integer', '2'],
    ['krw_million', 1_499_999, 'integer', '1'],
    ['krw_million', 2_500_000, 'integer', '3'],
    ['krw_million', 3_456_000_000, 'integer', '3,456'],
    ['decimal1', 2.25, 'decimal', '2.3'],
    ['decimal1', 2.24, 'decimal', '2.2'],
    ['decimal1', 12, 'integer', '12.0'],
  ] as const)('formats numbers by column format: %s %s', (format, value, valueType, expected) => {
    expect(formatCell(value, number(format, { valueType }), CTX)).toBe(expected)
  })

  it('shows a dash for an empty cell in every kind of column', () => {
    expect(formatCell(null, number('krw_thousand'), CTX)).toBe('—')
    expect(formatCell(null, resultColumn(), CTX)).toBe('—')
    expect(formatCell(null, resultColumn({ type: 'date', valueType: 'date', format: 'ymd' }), CTX)).toBe('—')
  })

  it('separates the thousands of a count on a text column', () => {
    const column = resultColumn({ valueType: 'integer', aggregate: 'count' })

    expect(formatCell(12_345, column, CTX)).toBe('12,345')
    expect(formatCell(0, resultColumn({ valueType: 'integer', aggregate: 'count_distinct' }), CTX)).toBe('0')
  })
})

describe('formatCell percent share (AC12)', () => {
  const share = (aggregate: 'sum' | 'count' | 'avg' | null) => number('percent_share', { index: 1, aggregate })

  it('formats percent share against totals only for sum and count', () => {
    const ctx = { ...CTX, totals: [null, 1000] }

    expect(formatCell(250, share('sum'), ctx)).toBe('25.0%')
    expect(formatCell(1, resultColumn({ index: 1, valueType: 'integer', format: 'percent_share', aggregate: 'count' }), { ...CTX, totals: [null, 3] })).toBe('33.3%')
    expect(formatCell(250, share('avg'), ctx)).toBe('250')
    expect(formatCell(250, share(null), ctx)).toBe('250')
  })

  it.each([
    [1445, 10_000, '14.5%'],
    [4445, 10_000, '44.5%'],
    [2255, 10_000, '22.6%'],
    [2885, 20_000, '14.4%'],
    [5, 40, '12.5%'],
  ])('rounds the share of %i in %i half up to one decimal', (value, total, expected) => {
    expect(formatCell(value, share('sum'), { ...CTX, totals: [null, total] })).toBe(expected)
  })

  it('falls back to separated thousands without usable totals', () => {
    expect(formatCell(1250, share('sum'), CTX)).toBe('1,250')
    expect(formatCell(1250, share('sum'), { ...CTX, totals: [null, 0] })).toBe('1,250')
    expect(formatCell(1250, share('sum'), { ...CTX, totals: [null, null] })).toBe('1,250')
  })

  it('reads the total of the same column index', () => {
    const column = number('percent_share', { index: 2, aggregate: 'sum' })

    expect(formatCell(50, column, { ...CTX, totals: [null, 999, 200] })).toBe('25.0%')
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
    expect(formatCell(1_234_567, number('thousands', { prefixLength: 3 }), CTX)).toBe('1,234,567')
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
    expect(formatShownCell(1_234_567, number('thousands', { prefixLength: 3 }), CTX)).toBe('1,2…')
  })

  it('cuts the formatted string of a date', () => {
    const column = resultColumn({ field: 'deal.expected_close', type: 'date', valueType: 'date', format: 'weekday', prefixLength: 4 })

    expect(formatShownCell('2026-10-27', column, CTX)).toBe('2026…')
  })

  it('never cuts an empty value dash', () => {
    expect(formatShownCell(null, resultColumn({ prefixLength: 1 }), CTX)).toBe('—')
  })

  it('shows the whole formatted value without a prefix length', () => {
    expect(formatShownCell(1_234_567, number('thousands'), CTX)).toBe('1,234,567')
    expect(formatShownCell('ABCDEF', resultColumn(), CTX)).toBe('ABCDEF')
  })
})

describe('cellTitle (AC17)', () => {
  it('gives the whole formatted value when the cell is cut, whatever the type', () => {
    expect(cellTitle(1_234_567, number('thousands', { prefixLength: 3 }), CTX)).toBe('1,234,567')
    expect(cellTitle('ABCDEF', resultColumn({ prefixLength: 3 }), CTX)).toBe('ABCDEF')
  })

  it('gives the text of a text cell that is not cut', () => {
    expect(cellTitle('긴 문장입니다', resultColumn(), CTX)).toBe('긴 문장입니다')
    expect(cellTitle('ABC', resultColumn({ prefixLength: 3 }), CTX)).toBe('ABC')
  })

  it('gives nothing for an empty cell or a number that is not cut', () => {
    expect(cellTitle(null, resultColumn(), CTX)).toBeUndefined()
    expect(cellTitle(1234, number('thousands'), CTX)).toBeUndefined()
    expect(cellTitle(12, number('thousands', { prefixLength: 5 }), CTX)).toBeUndefined()
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

describe('columnHeader (AC12)', () => {
  it('adds the unit of an amount format to the header', () => {
    expect(columnHeader(number('krw_thousand', { label: '금액 합계' }))).toMatch(/^금액 합계\s?\(천원\)$/)
    expect(columnHeader(number('krw_million', { label: '금액 합계' }))).toMatch(/^금액 합계\s?\(백만원\)$/)
  })

  it('keeps the label of every other format', () => {
    expect(columnHeader(number('thousands', { label: 'Users 합계' }))).toBe('Users 합계')
    expect(columnHeader(resultColumn({ label: 'Deal code' }))).toBe('Deal code')
  })
})
