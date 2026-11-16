import { describe, expect, it } from 'vitest'
import type { Contact, ContactDraft, ContactRow } from '../../../shared/model/types'
import { contactChangeOf, draftOf, resolveSamePerson } from './contactInline'

const at = '2026-11-01T09:00:00+09:00'
const contactA: Contact = { id: 1, kind: 'customer', company: '한빛은행', name: '정민수', title: '과장', email: 'jung@hanbit.test', phone: '010-2345-6789', createdAt: at, updatedAt: at }
const rowB: ContactRow = { id: 2, kind: 'customer', company: '한빛은행', name: '오지현', title: '차장', email: 'oh@hanbit.test', phone: '010-3456-7890', createdAt: at, updatedAt: at, dealCount: 1 }
const rows: readonly ContactRow[] = [{ ...contactA, dealCount: 2 }, rowB]

describe('contactChangeOf: 연락처 저장 결과 구분', () => {
  // 연락처 저장 결과 구분(변경 없음·연락 정보 수정·담당자 변경·연락처 변경)이 표대로 답한다.
  // 테스트 코드: DD-131
  it('classifies the save result as none, detail, person or session as DD-R34 says', () => {
    // given: 현재 연락처 A(한빛은행, id 1)
    const same = draftOf(contactA)
    // when / then: 값이 그대로면 변경 없음(null)
    expect(contactChangeOf(contactA, same)).toBeNull()
    // then: 같은 연락처 id에서 직급만 다르면 연락 정보 수정
    expect(contactChangeOf(contactA, { ...same, title: '부장' })).toBe('detail')
    // then: 같은 id에서 회사명이 대소문자만 달라도 연락 정보 수정(영문 회사명 연락처)
    const english: Contact = { ...contactA, company: 'Hanbit' }
    expect(contactChangeOf(english, draftOf(english))).toBeNull()
    expect(contactChangeOf(english, { ...draftOf(english), company: 'HANBIT' })).toBe('detail')
    // then: 같은 회사의 다른 담당자(id 2)는 담당자 변경
    expect(contactChangeOf(contactA, draftOf(rowB))).toBe('person')
    // then: id 없는 같은 회사의 새 이름도 담당자 변경
    const fresh: ContactDraft = { contactId: null, company: '한빛은행', name: '신입담당', title: '', email: null, phone: null }
    expect(contactChangeOf(contactA, fresh)).toBe('person')
    // then: 다른 회사는 연락처 변경
    expect(contactChangeOf(contactA, { ...fresh, company: '누리통신' })).toBe('session')
    // then: 현재 연락처가 없으면 새 입력은 연락처 변경
    expect(contactChangeOf(null, fresh)).toBe('session')
  })

  // 회사명 대소문자만 다른 새 담당자는 같은 회사로 본다(담당자 변경).
  // 테스트 코드: DD-131
  it('treats a new person under a company written in another case as the same company', () => {
    // given: 한빛은행 연락처와 회사명을 대문자로 쓴 새 담당자
    const draft: ContactDraft = { contactId: null, company: '한빛은행', name: 'Kim', title: '', email: null, phone: null }
    const cased = { ...contactA, company: 'Hanbit' }
    // when / then: 대소문자 무시 같은 회사면 담당자 변경
    expect(contactChangeOf(cased, { ...draft, company: 'HANBIT' })).toBe('person')
  })
})

describe('resolveSamePerson: 같은 이름 담당자 판정', () => {
  const typed: ContactDraft = { contactId: null, company: '한빛은행', name: '오지현'.toUpperCase(), title: '', email: null, phone: null }

  // 연결 연락처 없이 이메일이 비고 같은 이름(대소문자 무시)이면 그 담당자의 연락 정보를 쓴다.
  // 테스트 코드: DD-131
  it('returns the existing person when the name matches and the email is empty', () => {
    // given: 대소문자만 다른 이름("오지현"은 한글이라 영문 행으로도 확인)과 이메일 없는 입력
    const english: ContactRow = { ...rowB, id: 3, name: 'Oh Jihyun' }
    // when / then: 한글 이름은 그대로 일치해 B 정보(id 2)를 돌려준다
    expect(resolveSamePerson(rows, { ...typed, name: '오지현' })).toEqual(draftOf(rowB))
    // then: 대소문자만 다른 영문 이름도 같은 담당자로 본다
    expect(resolveSamePerson([english], { ...typed, name: 'OH JIHYUN' })).toEqual(draftOf(english))
  })

  // 이메일이 있으면 입력 그대로 둔다.
  // 테스트 코드: DD-131
  it('keeps the input as is when the email is filled', () => {
    // given: 같은 이름이지만 이메일이 있는 입력
    const withEmail: ContactDraft = { ...typed, name: '오지현', email: 'other@hanbit.test' }
    // when / then: 입력 그대로
    expect(resolveSamePerson(rows, withEmail)).toEqual(withEmail)
  })

  // 이미 연결 연락처가 있거나 같은 이름이 없으면 입력 그대로 둔다(경계).
  // 테스트 코드: DD-131
  it('keeps the input when it is already linked or no person has that name', () => {
    // given: 연결된 입력과 이름이 없는 입력
    const linked: ContactDraft = { ...typed, name: '오지현', contactId: 9 }
    const unknown: ContactDraft = { ...typed, name: '없는사람' }
    // when / then: 둘 다 입력 그대로
    expect(resolveSamePerson(rows, linked)).toEqual(linked)
    expect(resolveSamePerson(rows, unknown)).toEqual(unknown)
  })
})
