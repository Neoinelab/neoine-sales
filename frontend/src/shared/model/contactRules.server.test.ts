/** 규칙 대응표: 서버 `Email`·`PhoneNumber` 값 객체(backend/src/app/domain/common/contact.py)와 같은 경계값. */

import { describe, expect, it } from 'vitest'
import { EMAIL_FORMAT_MESSAGE, PHONE_FORMAT_MESSAGE, validateContactInput, WHITESPACE_MESSAGE } from './contactRules'

const withPhone = (phone: string | null) => validateContactInput({ company: 'A', name: 'B', title: '', email: null, phone })
const withEmail = (email: string | null) => validateContactInput({ company: 'A', name: 'B', title: '', email, phone: null })

describe('전화 형식(서버 PhoneNumber와 같다)', () => {
  // 전화 형식 오류 문구는 서버와 같다
  // 테스트 코드: CT-091
  it('문구', () => {
    // when: 문구 상수를 읽는다
    const message = PHONE_FORMAT_MESSAGE
    // then: 서버 문구와 같다
    expect(message).toBe('전화번호 형식이 올바르지 않습니다.')
  })

  // 서버 전화 형식(숫자 7~15개, 숫자·+-() 문자)에 맞는 값은 허용한다
  // 테스트 코드: CT-091
  it.each(['010-1234-5678', '+82-10-1234-5678', '02(123)4567', '1234567', '123456789012345', '+1-800-555-0100'])('%s 는 허용', (phone) => {
    // when: 서버 전화 형식에 맞는 값을 검증한다
    const result = withPhone(phone)
    // then: 오류가 없다
    expect(result).toEqual({})
  })

  // 서버 전화 형식을 벗어난 값은 형식 오류다
  // 테스트 코드: CT-091
  it.each([
    ['123456', '숫자 6자리(7 미만)'],
    ['1234567890123456', '숫자 16자리(15 초과)'],
    ['010-abcd-5678', '허용하지 않는 문자'],
    ['010.1234.5678', '점'],
    ['ext.1234567', '영문'],
    ['---+++()()', '숫자 없음'],
  ])('%s 는 형식 오류(%s)', (phone) => {
    // when: 서버 전화 형식을 벗어난 값을 검증한다
    const result = withPhone(phone)
    // then: 전화 형식 오류 문구다
    expect(result.phone).toBe(PHONE_FORMAT_MESSAGE)
  })

  // 전화에 공백이 있으면 형식보다 공백 오류가 먼저다
  // 테스트 코드: CT-091
  it('공백이 있으면 형식보다 공백 오류가 먼저다', () => {
    // when: 공백이 든 전화를 검증한다
    const result = withPhone('010 1234 5678').phone
    // then: 공백 오류다
    expect(result).toBe(WHITESPACE_MESSAGE)
  })

  // 전화가 없으면(null) 검사하지 않는다
  // 테스트 코드: CT-091
  it('없으면(null) 검사하지 않는다', () => {
    // when: 전화 null을 검증한다
    const result = withPhone(null)
    // then: 오류가 없다
    expect(result).toEqual({})
  })
})

describe('이메일 형식(서버 Email과 같다)', () => {
  // 서버 이메일 형식에 맞는 값은 허용한다
  // 테스트 코드: CT-091
  it.each(['a@b.co', 'hong.gildong@neoine.test', 'a@b.c.d', 'x+y@mail.example.org'])('%s 는 허용', (email) => {
    // when: 서버 이메일 형식에 맞는 값을 검증한다
    const result = withEmail(email)
    // then: 오류가 없다
    expect(result).toEqual({})
  })

  // 서버 이메일 형식에 맞지 않는 값은 형식 오류다
  // 테스트 코드: CT-091
  it.each(['nope', 'a@b', 'a@@b.co', '@b.co', 'a@.co', 'a@b.', 'a@b..co', 'a@b.co.', 'a@b@c.co'])('%s 는 형식 오류', (email) => {
    // when: 서버 이메일 형식에 맞지 않는 값을 검증한다
    const result = withEmail(email)
    // then: 이메일 형식 오류 문구다
    expect(result.email).toBe(EMAIL_FORMAT_MESSAGE)
  })

  // 이메일이 254자를 넘으면 형식 오류다
  // 테스트 코드: CT-091
  it('254자를 넘으면 형식 오류', () => {
    // when: 검증한다 (전제: 254자를 넘는 이메일)
    const long = `${'a'.repeat(250)}@b.co`
    // then: 형식 오류다
    expect(long.length).toBeGreaterThan(254)
    expect(withEmail(long).email).toBe(EMAIL_FORMAT_MESSAGE)
  })
})
