import { describe, expect, it } from 'vitest'
import { hasActiveFilter, listQueryFromParams } from './listQuery'

const params = (query: string) => new URLSearchParams(query)

/** URL owner_name(DL-R40)의 조회 조건 변환 규칙. */
describe('listQueryFromParams: owner_name', () => {
  it('owner_name은 앞뒤 공백을 지운 글자로 ownerName에 담긴다', () => {
    // when: 공백이 낀 owner_name을 바꾼다
    const actual = listQueryFromParams(params(`owner_name=${encodeURIComponent('  김영 ')}`))
    // then: 지운 글자가 ownerName이고 ownerId는 없다
    expect(actual).toEqual({ offset: 0, limit: 20, ownerName: '김영' })
  })

  it('공백뿐이거나 100자를 넘는 owner_name은 조회에 쓰지 않는다', () => {
    // when: 공백뿐인 값, 100자, 101자를 각각 바꾼다
    const blank = listQueryFromParams(params('owner_name=%20%20'))
    const max = listQueryFromParams(params(`owner_name=${'a'.repeat(100)}`))
    const over = listQueryFromParams(params(`owner_name=${'a'.repeat(101)}`))
    // then: 공백뿐인 값과 101자는 무시되고 100자는 쓰인다
    expect(blank).toEqual({ offset: 0, limit: 20 })
    expect(over).toEqual({ offset: 0, limit: 20 })
    expect(max.ownerName).toBe('a'.repeat(100))
  })

  it('owner_name이 있으면 owner는 조회에 쓰지 않는다', () => {
    // when: 둘 다 든 URL과 owner만 든 URL을 바꾼다
    const both = listQueryFromParams(params('owner=3&owner_name=%EA%B9%80'))
    const idOnly = listQueryFromParams(params('owner=3'))
    // then: 둘 다 있으면 ownerName만, owner만 있으면 ownerId만 담긴다
    expect(both).toEqual({ offset: 0, limit: 20, ownerName: '김' })
    expect(idOnly).toEqual({ offset: 0, limit: 20, ownerId: 3 })
  })

  it('owner_name은 활성 조건이다', () => {
    // when: owner_name만 든 URL을 판정한다
    const actual = hasActiveFilter(params('owner_name=%EA%B9%80'))
    // then: 활성 조건이다
    expect(actual).toBe(true)
  })
})
