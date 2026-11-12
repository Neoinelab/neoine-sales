import { describe, expect, it } from 'vitest'
import { toChoice } from './catalogChoice'

const OPTIONS = [
  { id: 1, name: '미팅' },
  { id: 2, name: 'Demo' },
] as const

describe('toChoice', () => {
  // 빈 입력이나 공백뿐인 입력은 선택 안 함(null)이다.
  // 테스트 코드: CL-076
  it('returns null for a blank text', () => {
    // when: 빈 문자열과 공백만 있는 문자열을 선택으로 바꾼다
    const actual1 = toChoice('', OPTIONS)
    const actual2 = toChoice('   ', OPTIONS)

    // then: 둘 다 null이다
    expect(actual1).toBeNull()
    expect(actual2).toBeNull()
  })

  // 선택지와 이름이 같으면 {id}다.
  // 테스트 코드: CL-076
  it('returns the id of the option with the same name', () => {
    // when: '미팅'을 선택으로 바꾼다
    const actual = toChoice('미팅', OPTIONS)

    // then: {id: 1}이다
    expect(actual).toEqual({ id: 1 })
  })

  // 선택 id는 JSON 숫자로 보낸다.
  // 테스트 코드: CL-076
  it('sends catalog ids as JSON numbers', () => {
    // when: '미팅' 선택을 JSON으로 직렬화한다
    const actual = JSON.stringify(toChoice('미팅', OPTIONS))

    // then: id가 따옴표 없는 숫자다
    expect(actual).toBe('{"id":1}')
  })

  // 대소문자와 앞뒤 공백을 무시하고 같은 이름이면 {id}다.
  // 테스트 코드: CL-076
  it('returns the id for a case-insensitive match and ignores surrounding spaces', () => {
    // when: '  demo '와 'DEMO'를 선택으로 바꾼다
    const actual1 = toChoice('  demo ', OPTIONS)
    const actual2 = toChoice('DEMO', OPTIONS)

    // then: 둘 다 {id: 2}다
    expect(actual1).toEqual({ id: 2 })
    expect(actual2).toEqual({ id: 2 })
  })

  // 같은 이름의 선택지가 없으면 공백을 지운 {name}이다.
  // 테스트 코드: CL-076
  it('returns the trimmed name when no option has the same name', () => {
    // when: '  웨비나  '를 선택으로 바꾼다
    const actual = toChoice('  웨비나  ', OPTIONS)

    // then: {name: '웨비나'}다
    expect(actual).toEqual({ name: '웨비나' })
  })

  // 부분 일치는 같은 선택지로 보지 않는다.
  // 테스트 코드: CL-076
  it('does not treat a partial match as the same option', () => {
    // when: '미'를 선택으로 바꾼다
    const actual = toChoice('미', OPTIONS)

    // then: {name: '미'}다
    expect(actual).toEqual({ name: '미' })
  })

  // 선택지가 비어 있으면 항상 {name}이다.
  // 테스트 코드: CL-076
  it('returns a name when there are no options at all', () => {
    // when: 선택지 없이 '미팅'을 선택으로 바꾼다
    const actual = toChoice('미팅', [])

    // then: {name: '미팅'}이다
    expect(actual).toEqual({ name: '미팅' })
  })
})
