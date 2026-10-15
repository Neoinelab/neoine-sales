import { describe, expect, it } from 'vitest'
import { formatKrwFull, formatKrwShort, isValidAmount, parseAmount } from './money'

describe('formatKrwShort', () => {
  it('T-MONEY-01 백만 단위는 M으로 표기한다', () => {
    expect(formatKrwShort(180_000_000)).toBe('180M')
    expect(formatKrwShort(1_234_567)).toBe('1.23M')
    expect(formatKrwShort(1_500_000)).toBe('1.5M')
  })

  it('T-MONEY-02 10억 이상은 B로 표기한다', () => {
    expect(formatKrwShort(1_870_000_000)).toBe('1.87B')
    expect(formatKrwShort(1_000_000_000)).toBe('1B')
    expect(formatKrwShort(12_345_000_000)).toBe('12.35B')
  })

  it('T-MONEY-03 백만 미만은 콤마 숫자와 원이다', () => {
    expect(formatKrwShort(999_999)).toBe('999,999원')
    expect(formatKrwShort(0)).toBe('0원')
    expect(formatKrwShort(1)).toBe('1원')
  })

  it('T-MONEY-04 경계값', () => {
    expect(formatKrwShort(1_000_000)).toBe('1M')
    expect(formatKrwShort(999_999_999)).toBe('1,000M')
    expect(formatKrwShort(1_000_000_000)).toBe('1B')
  })
})

describe('formatKrwFull', () => {
  it('콤마 숫자와 원', () => {
    expect(formatKrwFull(1_870_000_000)).toBe('1,870,000,000원')
    expect(formatKrwFull(0)).toBe('0원')
  })
})

describe('parseAmount / isValidAmount', () => {
  it('콤마와 앞뒤 공백을 허용한다', () => {
    expect(parseAmount('1,870,000,000')).toBe(1_870_000_000)
    expect(parseAmount('  500 ')).toBe(500)
  })

  it('소수·음수·문자·빈 값·0은 null이다', () => {
    for (const text of ['', ' ', '1.5', '-3', 'abc', '0', '1 000', '1e3']) {
      expect(parseAmount(text)).toBeNull()
    }
  })

  it('isValidAmount는 1 이상의 안전 정수만 허용한다', () => {
    expect(isValidAmount(1)).toBe(true)
    expect(isValidAmount(0)).toBe(false)
    expect(isValidAmount(1.2)).toBe(false)
    expect(isValidAmount('3')).toBe(false)
    expect(isValidAmount(Number.MAX_SAFE_INTEGER + 2)).toBe(false)
  })
})
