import { describe, expect, it } from 'vitest'
import {
  AMOUNT_INPUT_MESSAGE,
  AMOUNT_LABEL,
  AMOUNT_TOO_LARGE_MESSAGE,
  REVENUE_AMOUNT_LABEL,
  WON_MAX,
  amountInputError,
  formatAmountInput,
  formatWon,
  formatWonAxis,
  isValidAmount,
  parseAmountInput,
} from './money'
import * as money from './money'

// 백엔드 tests/unit/domain/test_krw_format.py와 같은 기준표
const SHOWN: [number, string][] = [
  [1_870_000_000, '1,870,000,000'],
  [150_000_000, '150,000,000'],
  [1_234_567, '1,234,567'],
  [1_234_499, '1,234,499'],
  [1_500, '1,500'],
  [300, '300'],
  [1, '1'],
  [0, '0'],
  [9_007_199_254_740_991, '9,007,199,254,740,991'],
]

describe('formatWon', () => {
  it.each(SHOWN)('formatWon adds commas without rounding: %i', (won, shown) => {
    expect(formatWon(won)).toBe(shown)
  })
})

describe('thousand-won helpers', () => {
  it('thousand-won helpers are removed', () => {
    const exported = money as Record<string, unknown>
    for (const name of ['toThousandWon', 'formatThousandWon', 'THOUSAND_WON_MAX', 'isSameShownAmount']) {
      expect(exported[name]).toBeUndefined()
    }
  })
})

describe('amount labels', () => {
  it('amount labels carry the won unit', () => {
    expect(AMOUNT_LABEL).toBe('금액(단위:원)')
    expect(REVENUE_AMOUNT_LABEL).toBe('매출금액(단위:원, 실제 값)')
    expect(WON_MAX).toBe(Number.MAX_SAFE_INTEGER)
  })
})

describe('parseAmountInput', () => {
  it('parseAmountInput reads won as typed', () => {
    expect(parseAmountInput('1,870,000,000')).toBe(1_870_000_000)
    expect(parseAmountInput(' 500 ')).toBe(500)
    expect(parseAmountInput('9,007,199,254,740,991')).toBe(Number.MAX_SAFE_INTEGER)
  })

  it('parseAmountInput rejects invalid input', () => {
    for (const text of ['', ' ', '0', '1.5', '-3', 'abc', '1 000', '1e3', '9007199254740992']) {
      expect(parseAmountInput(text)).toBeNull()
    }
  })
})

describe('amountInputError', () => {
  it('amountInputError tells which rule failed', () => {
    expect(amountInputError('')).toBe(AMOUNT_INPUT_MESSAGE)
    expect(amountInputError('0')).toBe(AMOUNT_INPUT_MESSAGE)
    expect(amountInputError('9,007,199,254,740,992')).toBe(AMOUNT_TOO_LARGE_MESSAGE)
    expect(amountInputError('1')).toBeNull()
    expect(amountInputError('9,007,199,254,740,991')).toBeNull()
  })

  it('amount messages state the won rule', () => {
    expect(AMOUNT_INPUT_MESSAGE).toBe('매출금액은 1원 이상의 정수를 입력하세요.')
    expect(AMOUNT_TOO_LARGE_MESSAGE).toBe(
      '매출금액은 9,007,199,254,740,991원 이하로 입력하세요.',
    )
  })
})

describe('formatWonAxis boundaries', () => {
  it.each([
    [99_999_999, '1억'],
    [99_999_500, '1억'],
    [99_995_000, '9,999.5만'],
    [9_999_999, '1,000만'],
    [10_000, '1만'],
    [9_999, '9,999'],
    [-99_999_999, '-1억'],
    [-99_999_500, '-1억'],
    [-9_999_999, '-1,000만'],
    [-9_999, '-9,999'],
  ])('rounds first and then picks the unit: %i', (value, shown) => {
    expect(formatWonAxis(value)).toBe(shown)
  })

  it('shows negative zero as 0', () => {
    expect(formatWonAxis(-0)).toBe('0')
  })
})

describe('formatWonAxis', () => {
  it.each([
    [1_870_000_000, '18.7억'],
    [100_000_000, '1억'],
    [123_400_000_000, '1,234억'],
    [50_000_000, '5,000만'],
    [15_000, '1.5만'],
    [9_000, '9,000'],
    [0, '0'],
    [-50_000_000, '-5,000만'],
  ])('formatWonAxis shortens ticks to eok and man: %i', (value, shown) => {
    expect(formatWonAxis(value)).toBe(shown)
  })
})

describe('formatAmountInput', () => {
  it.each([
    ['12345', 5, '12,345', 6],
    ['1,2345', 6, '12,345', 6],
    ['1,9234', 3, '19,234', 2],
    ['1234', 1, '1,234', 1],
    [',234', 0, '234', 0],
    ['007', 3, '7', 1],
    ['0', 1, '0', 1],
    ['1a2.3', 5, '123', 3],
    ['', 0, '', 0],
    ['1,500,000.50', 12, '150,000,050', 11],
  ])('formatAmountInput keeps the caret after the same digit: %j @%i', (raw, caret, text, next) => {
    expect(formatAmountInput(raw, caret)).toEqual({ text, caret: next })
  })
})

describe('isValidAmount', () => {
  it('isValidAmount는 1 이상의 안전 정수만 허용한다', () => {
    expect(isValidAmount(1)).toBe(true)
    expect(isValidAmount(0)).toBe(false)
    expect(isValidAmount(1.2)).toBe(false)
    expect(isValidAmount('3')).toBe(false)
    expect(isValidAmount(Number.MAX_SAFE_INTEGER + 2)).toBe(false)
  })
})
