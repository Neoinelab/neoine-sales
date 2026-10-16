/** 규칙 대응표: 서버 `Email`·`PhoneNumber` 값 객체(backend/src/app/domain/common/contact.py)와 같은 경계값. */

import { describe, expect, it } from 'vitest'
import { EMAIL_FORMAT_MESSAGE, PHONE_FORMAT_MESSAGE, validateContactInput, WHITESPACE_MESSAGE } from './contactRules'

const withPhone = (phone: string | null) => validateContactInput({ company: 'A', name: 'B', title: '', email: null, phone })
const withEmail = (email: string | null) => validateContactInput({ company: 'A', name: 'B', title: '', email, phone: null })

describe('전화 형식(서버 PhoneNumber와 같다)', () => {
  it('문구', () => {
    expect(PHONE_FORMAT_MESSAGE).toBe('전화번호 형식이 올바르지 않습니다.')
  })

  it.each(['010-1234-5678', '+82-10-1234-5678', '02(123)4567', '1234567', '123456789012345', '+1-800-555-0100'])('%s 는 허용', (phone) => {
    expect(withPhone(phone)).toEqual({})
  })

  it.each([
    ['123456', '숫자 6자리(7 미만)'],
    ['1234567890123456', '숫자 16자리(15 초과)'],
    ['010-abcd-5678', '허용하지 않는 문자'],
    ['010.1234.5678', '점'],
    ['ext.1234567', '영문'],
    ['---+++()()', '숫자 없음'],
  ])('%s 는 형식 오류(%s)', (phone) => {
    expect(withPhone(phone).phone).toBe(PHONE_FORMAT_MESSAGE)
  })

  it('공백이 있으면 형식보다 공백 오류가 먼저다', () => {
    expect(withPhone('010 1234 5678').phone).toBe(WHITESPACE_MESSAGE)
  })

  it('없으면(null) 검사하지 않는다', () => {
    expect(withPhone(null)).toEqual({})
  })
})

describe('이메일 형식(서버 Email과 같다)', () => {
  it.each(['a@b.co', 'hong.gildong@neoine.test', 'a@b.c.d', 'x+y@mail.example.org'])('%s 는 허용', (email) => {
    expect(withEmail(email)).toEqual({})
  })

  it.each(['nope', 'a@b', 'a@@b.co', '@b.co', 'a@.co', 'a@b.', 'a@b..co', 'a@b.co.', 'a@b@c.co'])('%s 는 형식 오류', (email) => {
    expect(withEmail(email).email).toBe(EMAIL_FORMAT_MESSAGE)
  })

  it('254자를 넘으면 형식 오류', () => {
    const long = `${'a'.repeat(250)}@b.co`
    expect(long.length).toBeGreaterThan(254)
    expect(withEmail(long).email).toBe(EMAIL_FORMAT_MESSAGE)
  })
})
