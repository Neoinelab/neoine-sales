import { describe, expect, it } from 'vitest'
import { parseId } from './ids'

describe('parseId', () => {
  it.each([
    ['1', 1],
    ['42', 42],
    ['9007199254740991', 9007199254740991],
  ])('양의 안전 정수 %j은(는) 숫자 id로 받아들인다', (raw, expected) => {
    // when: 문자열을 id로 해석한다
    const result = parseId(raw)

    // then: 해당 정수가 돌아온다
    expect(result).toBe(expected)
  })

  it.each([
    ['빈 문자열', ''],
    ['0', '0'],
    ['음수', '-1'],
    ['음수 0', '-0'],
    ['더하기 부호', '+3'],
    ['소수', '1.5'],
    ['소수부가 0인 소수', '5.0'],
    ['앞자리 0', '01'],
    ['지수 표기', '1e3'],
    ['16진수', '0x10'],
    ['문자', 'abc'],
    ['숫자 뒤 문자', '12abc'],
    ['예전 사용자 키', 'u-kim'],
    ['uuid', '0f0e0d0c-0b0a-4908-8706-050403020100'],
    ['안전 범위보다 1 큰 수', '9007199254740992'],
    ['안전 범위를 한참 넘는 수', '99999999999999999999'],
    ['앞 공백', ' 7'],
    ['뒤 공백', '7 '],
    ['가운데 공백', '1 2'],
    ['줄바꿈', '7\n'],
    ['천 단위 구분', '1,000'],
    ['전각 숫자', '１２'],
    ['Infinity', 'Infinity'],
    ['NaN', 'NaN'],
  ])('%s은(는) id로 받아들이지 않는다', (_name, raw) => {
    // when: 문자열을 id로 해석한다
    const result = parseId(raw)

    // then: undefined가 돌아온다
    expect(result).toBeUndefined()
  })

  it.each([null, undefined])('%s은(는) id로 받아들이지 않는다', (raw) => {
    // when: 값을 id로 해석한다
    const result = parseId(raw)

    // then: undefined가 돌아온다
    expect(result).toBeUndefined()
  })
})
