import { describe, expect, it } from 'vitest'
import {
  contactsOfCompany,
  distinctCompanies,
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
  it('T-CONTACT-01 모든 공백 문자를 제거한다', () => {
    expect(stripWhitespace(' 한 빛\t은행　')).toBe('한빛은행')
    expect(hasWhitespace('a b')).toBe(true)
    expect(hasWhitespace('ab')).toBe(false)
  })

  it('T-CONTACT-02 회사/담당자/이메일/전화에 공백이 있으면 오류, 직급 내부 공백은 허용', () => {
    const errors = validateContactInput({ company: '한 빛', name: '정 민수', title: '수석 과장', email: 'a b@c.d', phone: '010 1234' })
    expect(errors.company).toBe(WHITESPACE_MESSAGE)
    expect(errors.name).toBe(WHITESPACE_MESSAGE)
    expect(errors.email).toBe(WHITESPACE_MESSAGE)
    expect(errors.phone).toBe(WHITESPACE_MESSAGE)
    expect(errors.title).toBeUndefined()
  })

  it('필수 누락과 이메일 형식', () => {
    expect(validateContactInput({ company: '', name: '', title: '', email: null, phone: null })).toEqual({
      company: '회사명을 입력하세요.',
      name: '담당자명을 입력하세요.',
    })
    expect(validateContactInput({ company: 'A', name: 'B', title: '', email: 'nope', phone: null }).email).toBe(
      '이메일 형식이 올바르지 않습니다.',
    )
    expect(validateContactInput({ company: 'A', name: 'B', title: '', email: 'a@b.test', phone: '010-1234-5678' })).toEqual({})
  })
})

describe('회사 목록', () => {
  it('T-CONTACT-03 대소문자만 다른 회사는 하나로 보고 먼저 등록된 표기를 쓴다', () => {
    expect(distinctCompanies(list, 'customer')).toEqual(['Acme', '누리통신', '한빛은행'].sort((a, b) => a.localeCompare(b, 'ko')))
    expect(distinctCompanies(list, 'partner')).toEqual(['한빛은행'])
  })

  it('회사별 담당자는 대소문자를 무시하고 이름 순이다', () => {
    expect(contactsOfCompany(list, 'customer', 'acme').map((c) => c.name)).toEqual(['김철수', '박철수'])
    expect(contactsOfCompany(list, 'customer', '한빛은행')).toHaveLength(2)
    expect(contactsOfCompany(list, 'partner', '한빛은행')).toHaveLength(1)
  })
})

describe('findSamePerson', () => {
  it('T-CONTACT-04 이메일이 없으면 회사+이름이 같은 연락처와 같은 사람이다', () => {
    expect(findSamePerson(list, 'customer', input('한빛은행', '오지현', null))?.id).toBe(2)
    expect(findSamePerson(list, 'customer', input('한빛은행', '정민수', null))?.id).toBe(1)
    expect(findSamePerson(list, 'customer', input('누리통신', '배성훈', null))?.id).toBe(3)
  })

  it('T-CONTACT-05 이메일이 다르면 동명이인이다', () => {
    expect(findSamePerson(list, 'customer', input('누리통신', '배성훈', 'bae3@nuri.test'))).toBeNull()
    expect(findSamePerson(list, 'customer', input('누리통신', '배성훈', 'BAE2@nuri.test'))?.id).toBe(4)
  })

  it('기존 연락처에 이메일이 없으면 이메일을 채워 같은 사람으로 본다', () => {
    expect(findSamePerson(list, 'customer', input('한빛은행', '오지현', 'oh@hanbit.test'))?.id).toBe(2)
  })

  it('구분이 다르면 비교하지 않고 excludeId는 자기 자신을 뺀다', () => {
    expect(findSamePerson(list, 'customer', input('한빛은행', '표성호', null))).toBeNull()
    expect(findSamePerson(list, 'customer', input('한빛은행', '오지현', null), 2)).toBeNull()
  })

  it('대소문자 무시', () => {
    expect(findSamePerson(list, 'customer', input('acme', '김철수', null))?.id).toBe(5)
  })
})
