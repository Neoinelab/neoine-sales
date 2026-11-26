import { describe, expect, it } from 'vitest'
import {
  findSamePerson,
  hasWhitespace,
  stripWhitespace,
  validateContactInput,
  WHITESPACE_MESSAGE,
} from './contactRules'
import type { Contact } from './types'

function contact(id: number, company: string, name: string, email: string | null, kind: Contact['kind'] = 'customer'): Contact {
  return { id, kind, company, name, title: '과장', email, phone: null, createdAt: '2026-01-01T00:00:00+09:00', updatedAt: '2026-01-01T00:00:00+09:00' }
}

const list: Contact[] = [
  contact(1, '한빛은행', '정민수', 'jung@hanbit.test'),
  contact(2, '한빛은행', '오지현', null),
  contact(3, '누리통신', '배성훈', 'bae1@nuri.test'),
  contact(4, '누리통신', '배성훈', 'bae2@nuri.test'),
  contact(5, 'Acme', '김철수', null),
  contact(6, 'ACME', '박철수', null),
  contact(1, '한빛은행', '표성호', null, 'partner'),
]
const input = (company: string, name: string, email: string | null) => ({ company, name, title: '', email, phone: null })

describe('공백 규칙', () => {
  // 모든 공백 문자(스페이스·탭·전각 공백)를 지우고 공백 여부를 판정한다
  // 테스트 코드: CT-091
  it('T-CONTACT-01 모든 공백 문자를 제거한다', () => {
    // when: 공백을 지우고 공백 여부를 본다 (전제: 스페이스·탭·전각 공백이 섞인 글)
    const actual1 = stripWhitespace(' 한 빛\t은행　')
    const actual2 = hasWhitespace('a b')
    const actual3 = hasWhitespace('ab')

    // then: 공백이 모두 사라지고 공백 판정이 맞다
    expect(actual1).toBe('한빛은행')
    expect(actual2).toBe(true)
    expect(actual3).toBe(false)
  })

  // 회사명·담당자명·이메일·전화의 공백은 오류이고 직급의 공백은 허용한다
  // 테스트 코드: CT-091
  it('T-CONTACT-02 회사/담당자/이메일/전화에 공백이 있으면 오류, 직급 내부 공백은 허용', () => {
    // when: 입력을 검증한다 (전제: 각 칸에 공백이 든 입력)
    const errors = validateContactInput({ company: '한 빛', name: '정 민수', title: '수석 과장', email: 'a b@c.d', phone: '010 1234' })

    // then: 네 칸은 공백 오류이고 직급은 오류가 없다
    expect(errors.company).toBeUndefined()
    expect(errors.name).toBe(WHITESPACE_MESSAGE)
    expect(errors.email).toBe(WHITESPACE_MESSAGE)
    expect(errors.phone).toBe(WHITESPACE_MESSAGE)
    expect(errors.title).toBeUndefined()
  })

  // 빈 회사명·담당자명은 필수 문구, 틀린 이메일은 형식 문구이고 올바른 입력은 오류가 없다
  // 테스트 코드: CT-091
  it('필수 누락과 이메일 형식', () => {
    // given: 빈 회사명·담당자명, 틀린 이메일, 올바른 입력
    const blank = { company: '', name: '', title: '', email: null, phone: null }
    const badEmail = { company: 'A', name: 'B', title: '', email: 'nope', phone: null }
    const valid = { company: 'A', name: 'B', title: '', email: 'a@b.test', phone: '010-1234-5678' }

    // when: 각각 검증한다
    const blankErrors = validateContactInput(blank)
    const badEmailErrors = validateContactInput(badEmail)
    const validErrors = validateContactInput(valid)

    // then: 필수 문구, 이메일 형식 문구, 빈 오류가 나온다
    expect(blankErrors).toEqual({
      company: '회사명을 입력하세요.',
      name: '담당자명을 입력하세요.',
    })
    expect(badEmailErrors.email).toBe('이메일 형식이 올바르지 않습니다.')
    expect(validErrors).toEqual({})
  })
})

describe('findSamePerson', () => {
  // 이메일 없이 입력하면 회사명·담당자명이 같은 기존 연락처와 같은 사람이다
  // 테스트 코드: CT-092
  it('T-CONTACT-04 이메일이 없으면 회사+이름이 같은 연락처와 같은 사람이다', () => {
    // when: 이메일 없는 입력으로 같은 사람을 찾는다 (전제: 이메일이 있는 연락처와 없는 연락처)
    const actual1 = findSamePerson(list, 'customer', input('한빛은행', '오지현', null))?.id
    const actual2 = findSamePerson(list, 'customer', input('한빛은행', '정민수', null))?.id
    const actual3 = findSamePerson(list, 'customer', input('누리통신', '배성훈', null))?.id

    // then: 회사명·담당자명이 같은 연락처 중 id가 작은 것이 나온다
    expect(actual1).toBe(2)
    expect(actual2).toBe(1)
    expect(actual3).toBe(3)
  })

  // 둘 다 이메일이 있고 다르면 동명이인이고 같으면(대소문자 무시) 같은 사람이다
  // 테스트 코드: CT-092
  it('T-CONTACT-05 이메일이 다르면 동명이인이다', () => {
    // when: 다른 이메일과 대소문자만 다른 이메일로 찾는다 (전제: 이메일이 서로 다른 동명이인 두 건)
    const actual1 = findSamePerson(list, 'customer', input('누리통신', '배성훈', 'bae3@nuri.test'))
    const actual2 = findSamePerson(list, 'customer', input('누리통신', '배성훈', 'BAE2@nuri.test'))?.id

    // then: 다른 이메일은 없음, 같은 이메일은 해당 연락처다
    expect(actual1).toBeNull()
    expect(actual2).toBe(4)
  })

  // 이메일 없는 기존 연락처에 이메일을 채운 입력은 같은 사람이다
  // 테스트 코드: CT-092
  it('기존 연락처에 이메일이 없으면 이메일을 채워 같은 사람으로 본다', () => {
    // when: 같은 이름에 이메일을 채워 찾는다 (전제: 이메일 없는 연락처)
    const actual = findSamePerson(list, 'customer', input('한빛은행', '오지현', 'oh@hanbit.test'))?.id

    // then: 그 연락처가 나온다
    expect(actual).toBe(2)
  })

  // 종류가 다르면 비교하지 않고 자기 자신은 후보에서 뺀다
  // 테스트 코드: CT-092
  it('구분이 다르면 비교하지 않고 excludeId는 자기 자신을 뺀다', () => {
    // when: 같은 사람을 찾는다 (전제: 다른 종류의 같은 이름과 자기 자신)
    const actual1 = findSamePerson(list, 'customer', input('한빛은행', '표성호', null))
    const actual2 = findSamePerson(list, 'customer', input('한빛은행', '오지현', null), 2)

    // then: 없음(null)이다
    expect(actual1).toBeNull()
    expect(actual2).toBeNull()
  })

  // 회사명·담당자명은 대소문자를 무시하고 비교한다
  // 테스트 코드: CT-092
  it('대소문자 무시', () => {
    // when: 소문자 회사명으로 찾는다 (전제: 'ACME' 연락처 목록)
    const actual = findSamePerson(list, 'customer', input('acme', '김철수', null))?.id

    // then: 해당 연락처가 나온다
    expect(actual).toBe(5)
  })
})
