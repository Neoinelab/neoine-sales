import { describe, expect, it } from 'vitest'
import { toContactBody } from './contact'

describe('toContactBody', () => {
  // 쓰기 본문은 빈 직급을 null로 바꾸고 나머지 값은 그대로 둔다
  // 테스트 코드: CT-107
  it('sends an empty title as null and keeps the other fields', () => {
    // given: 직급이 빈 문자열인 입력
    const input = { company: 'A', name: 'B', title: '', email: 'a@b.co', phone: null }

    // when: 쓰기 본문으로 바꾼다
    const body = toContactBody(input)

    // then: 직급만 null이다
    expect(body).toEqual({
      company: 'A',
      name: 'B',
      title: null,
      email: 'a@b.co',
      phone: null,
    })
  })

  // 직급은 입력한 그대로 보낸다
  // 테스트 코드: CT-107
  it('keeps a title as typed', () => {
    // when: 쓰기 본문으로 바꾼다 (전제: 내부 공백이 있는 직급)
    const actual = toContactBody({ company: 'A', name: 'B', title: '팀 장', email: null, phone: null }).title

    // then: 그대로 남는다
    expect(actual).toBe('팀 장')
  })
})
