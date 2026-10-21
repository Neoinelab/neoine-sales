import { describe, expect, it } from 'vitest'
import { parseId } from './ids'

describe('parseId', () => {
  it.each([
    ['1', 1],
    ['42', 42],
    ['9007199254740991', 9007199254740991],
  ])('accepts the positive safe integer %j', (raw, expected) => {
    expect(parseId(raw)).toBe(expected)
  })

  it.each([
    ['empty text', ''],
    ['zero', '0'],
    ['negative', '-1'],
    ['negative zero', '-0'],
    ['plus sign', '+3'],
    ['decimal', '1.5'],
    ['decimal with zero fraction', '5.0'],
    ['leading zero', '01'],
    ['exponent', '1e3'],
    ['hex', '0x10'],
    ['letters', 'abc'],
    ['digits then letters', '12abc'],
    ['old user key', 'u-kim'],
    ['uuid', '0f0e0d0c-0b0a-4908-8706-050403020100'],
    ['one above the safe range', '9007199254740992'],
    ['far above the safe range', '99999999999999999999'],
    ['leading space', ' 7'],
    ['trailing space', '7 '],
    ['inner space', '1 2'],
    ['newline', '7\n'],
    ['thousands separator', '1,000'],
    ['full-width digits', '１２'],
    ['Infinity', 'Infinity'],
    ['NaN', 'NaN'],
  ])('rejects %s', (_name, raw) => {
    expect(parseId(raw)).toBeUndefined()
  })

  it.each([null, undefined])('rejects %s', (raw) => {
    expect(parseId(raw)).toBeUndefined()
  })
})
