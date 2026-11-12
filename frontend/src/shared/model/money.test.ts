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
  // 테스트 코드: UI-029
  it.each(SHOWN)('원 값 %i는 반올림 없이 콤마를 넣어 %s로 보인다', (won, shown) => {
    // when: 금액을 표시 글자로 바꾼다
    const text = formatWon(won)
    // then: 반올림 없는 콤마 숫자다
    expect(text).toBe(shown)
  })
})

describe('thousand-won helpers', () => {
  // 테스트 코드: UI-029
  it('천원 함수는 내보내지 않는다', () => {
    // when: 내보낸 이름을 본다
    const exported = money as Record<string, unknown>
    // then: 천원 함수와 상수가 없다
    for (const name of ['toThousandWon', 'formatThousandWon', 'THOUSAND_WON_MAX', 'isSameShownAmount']) {
      expect(exported[name]).toBeUndefined()
    }
  })
})

describe('amount labels', () => {
  // 테스트 코드: UI-026
  it('항목 이름은 원 단위를 가지고 상한은 안전 정수 상한이다', () => {
    // when: 항목 이름 상수와 상한 상수를 읽는다
    const labels = [AMOUNT_LABEL, REVENUE_AMOUNT_LABEL, WON_MAX]
    // then: 원 단위 기준이다
    expect(labels).toEqual(['금액(단위:원)', '매출금액(단위:원, 실제 값)', Number.MAX_SAFE_INTEGER])
  })
})

describe('parseAmountInput', () => {
  // 테스트 코드: UI-027
  it('1 이상 안전 정수 상한 이하의 숫자는 원 값으로 읽는다', () => {
    // when: 콤마·공백이 섞인 글자를 읽는다
    const big = parseAmountInput('1,870,000,000')
    const spaced = parseAmountInput(' 500 ')
    const max = parseAmountInput('9,007,199,254,740,991')
    // then: 원 값이다
    expect(big).toBe(1_870_000_000)
    expect(spaced).toBe(500)
    expect(max).toBe(Number.MAX_SAFE_INTEGER)
  })

  // 테스트 코드: UI-027
  it.each(['', ' ', '0', '1.5', '-3', 'abc', '1 000', '1e3', '9007199254740992'])('읽을 수 없는 %j는 null이다', (text) => {
    // when: 읽는다
    const value = parseAmountInput(text)
    // then: 거절한다
    expect(value).toBeNull()
  })
})

describe('amountInputError', () => {
  // 테스트 코드: UI-028
  it('빈 값과 0은 1원 이상 문구, 상한 초과는 상한 문구, 읽을 수 있으면 null이다', () => {
    // when: 글자별 문구를 구한다
    const empty = amountInputError('')
    const zero = amountInputError('0')
    const over = amountInputError('9,007,199,254,740,992')
    const one = amountInputError('1')
    const max = amountInputError('9,007,199,254,740,991')
    // then: 위반 종류별 문구다
    expect(empty).toBe(AMOUNT_INPUT_MESSAGE)
    expect(zero).toBe(AMOUNT_INPUT_MESSAGE)
    expect(over).toBe(AMOUNT_TOO_LARGE_MESSAGE)
    expect(one).toBeNull()
    expect(max).toBeNull()
  })

  // 테스트 코드: UI-028
  it('문구는 원 단위 규칙을 그대로 말한다', () => {
    // when: 문구 상수를 읽는다
    const messages = [AMOUNT_INPUT_MESSAGE, AMOUNT_TOO_LARGE_MESSAGE]
    // then: 원 단위 규칙을 말한다
    expect(messages).toEqual([
      '매출금액은 1원 이상의 정수를 입력하세요.',
      '매출금액은 9,007,199,254,740,991원 이하로 입력하세요.',
    ])
  })
})

describe('formatWonAxis boundaries', () => {
  // 테스트 코드: UI-030
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
  ])('반올림한 뒤 단위를 정한다: %i는 %s', (value, shown) => {
    // when: 축 눈금 글자로 줄인다
    const text = formatWonAxis(value)
    // then: 반올림 뒤 억·만 단위다
    expect(text).toBe(shown)
  })

  // 테스트 코드: UI-030
  it('음수 0은 0으로 보인다', () => {
    // when: 줄인다
    const text = formatWonAxis(-0)
    // then: 부호 없는 0이다
    expect(text).toBe('0')
  })
})

describe('formatWonAxis', () => {
  // 테스트 코드: UI-030
  it.each([
    [1_870_000_000, '18.7억'],
    [100_000_000, '1억'],
    [123_400_000_000, '1,234억'],
    [50_000_000, '5,000만'],
    [15_000, '1.5만'],
    [9_000, '9,000'],
    [0, '0'],
    [-50_000_000, '-5,000만'],
  ])('차트 축 금액 %i는 억·만 단위 %s로 줄인다', (value, shown) => {
    // when: 축 눈금 글자로 줄인다
    const text = formatWonAxis(value)
    // then: 억·만 단위다
    expect(text).toBe(shown)
  })
})

describe('formatAmountInput', () => {
  // 테스트 코드: UI-024
  it.each([
    ['12345', 5, '12,345', 6],
    ['1,2345', 6, '12,345', 6],
    ['1,9234', 3, '19,234', 2],
    ['1234', 1, '1,234', 1],
    [',234', 0, '234', 0],
  ])('콤마를 다시 넣어도 캐럿은 같은 숫자 뒤에 남는다: %j @%i', (raw, caret, text, next) => {
    // when: 글자와 캐럿을 정리한다
    const formatted = formatAmountInput(raw, caret)
    // then: 같은 숫자 뒤에 캐럿이 있다
    expect(formatted).toEqual({ text, caret: next })
  })

  // 테스트 코드: UI-025
  it.each([
    ['007', 3, '7', 1],
    ['0', 1, '0', 1],
    ['1a2.3', 5, '123', 3],
    ['', 0, '', 0],
    ['1,500,000.50', 12, '150,000,050', 11],
  ])('앞자리 0과 숫자 아닌 글자를 정리한다: %j @%i', (raw, caret, text, next) => {
    // when: 글자와 캐럿을 정리한다
    const formatted = formatAmountInput(raw, caret)
    // then: 앞자리 0이 지워지고 숫자만 남는다
    expect(formatted).toEqual({ text, caret: next })
  })
})

describe('isValidAmount', () => {
  // 테스트 코드: UI-027
  it('isValidAmount는 1 이상의 안전 정수만 허용한다', () => {
    // when: 값을 판정한다
    const one = isValidAmount(1)
    const zero = isValidAmount(0)
    const fraction = isValidAmount(1.2)
    const text = isValidAmount('3')
    const over = isValidAmount(Number.MAX_SAFE_INTEGER + 2)
    // then: 1만 참이다
    expect(one).toBe(true)
    expect(zero).toBe(false)
    expect(fraction).toBe(false)
    expect(text).toBe(false)
    expect(over).toBe(false)
  })
})
