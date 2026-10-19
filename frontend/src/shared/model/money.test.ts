import { describe, expect, it } from 'vitest'
import {
  AMOUNT_INPUT_MESSAGE,
  AMOUNT_LABEL,
  AMOUNT_TOO_LARGE_MESSAGE,
  REVENUE_AMOUNT_LABEL,
  THOUSAND_WON_MAX,
  amountInputError,
  formatAmountInput,
  formatThousandWon,
  isSameShownAmount,
  isValidAmount,
  parseAmountInput,
  toThousandWon,
} from './money'

// 백엔드 tests/unit/domain/test_krw_format.py와 같은 기준표
const SHOWN: [number, string][] = [
  [1_870_000_000, '1,870,000'],
  [150_000_000, '150,000'],
  [1_000, '1'],
  [1_234_567, '1,235'],
  [1_234_499, '1,234'],
  [1_500, '2'],
  [2_500, '3'],
  [499, '0'],
  [500, '1'],
  [0, '0'],
  [9_007_199_254_740_991, '9,007,199,254,741'],
]

describe('formatThousandWon', () => {
  it.each(SHOWN)('formatThousandWon rounds half-up with commas and no unit: %i', (won, shown) => {
    expect(formatThousandWon(won)).toBe(shown)
  })
})

describe('toThousandWon', () => {
  it('toThousandWon is exact at the safe integer limit', () => {
    expect(toThousandWon(Number.MAX_SAFE_INTEGER)).toBe(9_007_199_254_741)
    expect(toThousandWon(2_500)).toBe(3)
    expect(toThousandWon(1_499)).toBe(1)
    expect(toThousandWon(0)).toBe(0)
  })
})

describe('amount labels', () => {
  it('amount labels carry the thousand-won unit', () => {
    expect(AMOUNT_LABEL).toBe('금액(단위:천원)')
    expect(REVENUE_AMOUNT_LABEL).toBe('매출금액(단위:천원, 실제 값)')
    expect(THOUSAND_WON_MAX).toBe(9_007_199_254_740)
  })
})

describe('parseAmountInput', () => {
  it('parseAmountInput converts thousands to won', () => {
    expect(parseAmountInput('1,870,000')).toBe(1_870_000_000)
    expect(parseAmountInput(' 500 ')).toBe(500_000)
    expect(parseAmountInput('9,007,199,254,740')).toBe(9_007_199_254_740_000)
  })

  it('parseAmountInput rejects invalid input', () => {
    for (const text of ['', ' ', '0', '1.5', '-3', 'abc', '1 000', '1e3', '9007199254741']) {
      expect(parseAmountInput(text)).toBeNull()
    }
  })
})

describe('amountInputError', () => {
  it('amountInputError tells which rule failed', () => {
    expect(amountInputError('')).toBe(AMOUNT_INPUT_MESSAGE)
    expect(amountInputError('0')).toBe(AMOUNT_INPUT_MESSAGE)
    expect(amountInputError('9,007,199,254,741')).toBe(AMOUNT_TOO_LARGE_MESSAGE)
    expect(amountInputError('1')).toBeNull()
    expect(amountInputError('9,007,199,254,740')).toBeNull()
  })

  it('amount messages state the thousand-won rule', () => {
    expect(AMOUNT_INPUT_MESSAGE).toBe('매출금액은 천원 단위로 1 이상의 정수를 입력하세요.')
    expect(AMOUNT_TOO_LARGE_MESSAGE).toBe(
      '매출금액은 천원 단위로 9,007,199,254,740 이하로 입력하세요.',
    )
  })
})

describe('isSameShownAmount', () => {
  it('isSameShownAmount compares the shown thousands', () => {
    expect(isSameShownAmount(1_235_000, 1_234_567)).toBe(true)
    expect(isSameShownAmount(1_234_000, 1_234_567)).toBe(false)
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
