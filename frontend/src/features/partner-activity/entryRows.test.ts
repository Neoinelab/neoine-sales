import { describe, expect, it } from 'vitest'
import { dateValueError } from '../../shared/model/dateText'
import { MAX_ROWS, applyServerErrors, emptyRow, firstMissingField, isBlank, isComplete, rowsToInputs, validateRows, type EntryRow } from './entryRows'

const TODAY = '2027-03-15'

/** 모두 채워진 행. 고르기 전의 글자(partnerText)와 고른 값(partnerCompany)을 따로 둔다. Deal 칸은 없다. */
function row(over: Partial<EntryRow> = {}): EntryRow {
  return {
    key: 'k',
    partnerText: '코어테크',
    partnerCompany: '코어테크',
    meetingDate: '2027-03-10',
    content: '견적 전달',
    ...over,
  }
}

describe('emptyRow', () => {
  // 빈 행은 받은 날짜와 고유 key를 갖고 나머지는 비어 있다.
  it('starts empty with the given date and a key of its own', () => {
    // when: 같은 날짜로 빈 행을 두 번 만든다
    const a = emptyRow(TODAY)
    const b = emptyRow(TODAY)
    // then: 날짜만 채워지고 key가 서로 다르며 Deal 키가 없다
    expect(a).toMatchObject({ partnerText: '', partnerCompany: '', meetingDate: TODAY, content: '' })
    expect(a.key).not.toBe(b.key)
    expect(Object.keys(a).sort()).toEqual(['content', 'key', 'meetingDate', 'partnerCompany', 'partnerText'])
  })

  // 행은 최대 50개다.
  it('caps the rows at 50', () => {
    // when·then: 상수 MAX_ROWS를 읽으면 50이다
    expect(MAX_ROWS).toBe(50)
  })
})

describe('isBlank', () => {
  // 기본 날짜만 있는 행은 빈 행이다.
  it('ignores the date: an untouched row with the default date is blank', () => {
    // when: 건드리지 않은 행이 비었는지 본다
    const blank = isBlank(emptyRow(TODAY))
    // then: 비었다
    expect(blank).toBe(true)
  })

  // 파트너 글자·고른 파트너·내용 중 하나라도 있으면 빈 행이 아니다.
  it.each([
    ['a typed partner', { partnerText: '코' }],
    ['a chosen partner', { partnerCompany: '코어테크' }],
    ['a content', { content: '내용' }],
  ])('is not blank with %s', (_name, over) => {
    // when: 그 칸이 채워진 행이 비었는지 본다
    const blank = isBlank({ ...emptyRow(TODAY), ...over })
    // then: 비어 있지 않다
    expect(blank).toBe(false)
  })

  // 공백뿐인 내용은 빈 것으로 본다.
  it('treats a whitespace-only content as blank', () => {
    // when: 공백뿐인 내용의 행이 비었는지 본다
    const blank = isBlank({ ...emptyRow(TODAY), content: '  \n ' })
    // then: 비었다
    expect(blank).toBe(true)
  })
})

describe('isComplete and firstMissingField', () => {
  // 파트너·올바른 날짜·내용이 있는 행은 완성이다(Deal 없이).
  it('a row with a partner, a valid date and content is complete without any deal', () => {
    // when: 모두 채운 행을 검사한다
    const complete = isComplete(row())
    const missing = firstMissingField(row())
    // then: 완성이고 빠진 칸이 없다
    expect(complete).toBe(true)
    expect(missing).toBeNull()
  })

  // 빠졌거나 틀린 칸이 첫 빠진 칸으로 보고된다.
  it.each([
    ['partnerCompany', { partnerCompany: '' }],
    ['meetingDate', { meetingDate: '' }],
    ['meetingDate', { meetingDate: '2027.03' }],
    ['meetingDate', { meetingDate: '2027.13.45' }],
    ['content', { content: '   ' }],
  ] as const)('reports %s when it is missing or wrong', (field, over) => {
    // when: 그 칸이 빠진 행을 검사한다
    const complete = isComplete(row(over))
    const missing = firstMissingField(row(over))
    // then: 미완성이고 그 칸이 첫 빠진 칸이다
    expect(complete).toBe(false)
    expect(missing).toBe(field)
  })

  // 첫 빠진 칸은 파트너, 날짜, 내용 순이다.
  it('reports the first missing field in the order partner, date, content', () => {
    // when: 파트너·내용이 빠진 행과 날짜·내용이 빠진 행을 검사한다
    const partnerFirst = firstMissingField(row({ partnerCompany: '', content: '' }))
    const dateFirst = firstMissingField(row({ meetingDate: '2027.03', content: '' }))
    // then: 각각 파트너, 날짜가 먼저다
    expect(partnerFirst).toBe('partnerCompany')
    expect(dateFirst).toBe('meetingDate')
  })

  // 글자만 친 파트너는 고른 것으로 보지 않는다.
  it('does not accept a typed-only partner (nothing chosen from the list)', () => {
    // when: 글자만 친 파트너의 행을 검사한다
    const missing = firstMissingField(row({ partnerCompany: '', partnerText: '코어' }))
    // then: 파트너가 빠졌다고 본다
    expect(missing).toBe('partnerCompany')
  })
})

describe('validateRows', () => {
  // 빈 행은 건너뛰고 완성 행은 통과한다.
  it('skips blank rows and passes complete rows', () => {
    // when: 빈 행·완성 행·빈 행을 검사한다
    const errors = validateRows([emptyRow(TODAY), row(), emptyRow(TODAY)])
    // then: 오류가 없다
    expect(errors).toEqual({})
  })

  // 덜 채운 행은 칸마다 정해진 문구를 모두 보고한다.
  it('reports every problem of a partly filled row with the planned messages', () => {
    // when: 파트너·날짜·내용이 모두 빠진 행을 검사한다
    const errors = validateRows([row({ partnerCompany: '', partnerText: '코', meetingDate: '', content: '' })])
    // then: 세 칸의 문구가 모두 나온다
    expect(errors).toEqual({
      0: {
        partnerCompany: '파트너를 선택하세요.',
        meetingDate: '미팅 날짜를 입력하세요.',
        content: '미팅 내용을 입력하세요.',
      },
    })
  })

  // 어떤 문구에도 Deal이 없다.
  it('never asks for a deal', () => {
    // when: 모든 칸이 빠진 행을 검사한다
    const errors = validateRows([row({ partnerCompany: '', meetingDate: '', content: '' })])
    // then: 오류에 Deal이 없다
    expect(JSON.stringify(errors)).not.toContain('Deal')
  })

  // 틀린 날짜는 날짜 규칙의 문구를 쓴다.
  it('uses the date message of the date rules for a wrong date', () => {
    // when: 날짜가 덜 쳐진 행을 검사한다
    const errors = validateRows([row({ meetingDate: '2027.03' })])
    // then: 날짜 규칙의 문구다
    expect(errors[0]).toEqual({ meetingDate: dateValueError('2027.03') })
  })

  // 오류 키는 빈 행을 포함한 화면 순서의 위치다.
  it('keys the errors by the position in the given rows, not among the non-blank rows', () => {
    // when: 빈 행, 완성 행, 내용 없는 행을 검사한다
    const errors = validateRows([emptyRow(TODAY), row(), row({ content: '' })])
    // then: 오류 키는 2뿐이다
    expect(Object.keys(errors)).toEqual(['2'])
    expect(errors[2]).toEqual({ content: '미팅 내용을 입력하세요.' })
  })

  // 빈 행의 날짜는 보지 않는다.
  it('does not look at the date of a blank row', () => {
    // when: 틀린 날짜를 가진 빈 행을 검사한다
    const errors = validateRows([{ ...emptyRow(TODAY), meetingDate: '2027.03' }])
    // then: 오류가 없다
    expect(errors).toEqual({})
  })
})

describe('rowsToInputs', () => {
  // 빈 행이 아닌 행의 세 값만 순서대로 보내고 어느 화면 행인지 기억한다.
  it('rowsToInputs sends only the three fields of the non-blank rows in order and remembers which row each input came from', () => {
    // when: 빈 행이 섞인 네 행을 요청 항목으로 바꾼다
    const result = rowsToInputs([emptyRow(TODAY), row({ content: '첫째' }), emptyRow(TODAY), row({ content: '둘째', meetingDate: '2027-03-11' })])
    // then: 채운 두 행의 세 값만 순서대로 담기고 원래 행 위치를 기억한다
    expect(result.inputs).toStrictEqual([
      { partnerCompany: '코어테크', meetingDate: '2027-03-10', content: '첫째' },
      { partnerCompany: '코어테크', meetingDate: '2027-03-11', content: '둘째' },
    ])
    expect(result.rowIndexOf).toEqual([1, 3])
  })

  // 모든 행이 비었으면 보낼 것이 없다.
  it('returns nothing when every row is blank', () => {
    // when: 빈 행만 요청 항목으로 바꾼다
    const result = rowsToInputs([emptyRow(TODAY), emptyRow(TODAY)])
    // then: 항목이 없다
    expect(result).toEqual({ inputs: [], rowIndexOf: [] })
  })
})

describe('applyServerErrors', () => {
  const rows = [emptyRow(TODAY), row(), emptyRow(TODAY), row()]
  const { rowIndexOf } = rowsToInputs(rows)

  // 서버가 준 위치를 화면 행·칸으로 되돌린다.
  it('maps the located violations of the sent items back to the screen rows and fields', () => {
    // when: 보낸 항목 기준 위치의 위반 셋을 화면 오류로 바꾼다
    const errors = applyServerErrors(
      [
        { location: ['items', 1, 'content'], message: '미팅 내용을 입력하세요.' },
        { location: ['items', 1, 'meeting_date'], message: '범위 문구' },
        { location: ['items', 0, 'partner_company'], message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
      ],
      rowIndexOf,
    )
    // then: 화면의 1번·3번 행의 해당 칸에 문구가 놓인다
    expect(errors).toEqual({
      1: { partnerCompany: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
      3: { content: '미팅 내용을 입력하세요.', meetingDate: '범위 문구' },
    })
  })

  // 칸마다 첫 문구만 두고 놓을 수 없는 위치는 무시한다.
  it('keeps the first message of a field and ignores locations it cannot place', () => {
    // when: 같은 칸 위반 둘, 없는 행, 위치 없는 위반을 바꾼다
    const errors = applyServerErrors(
      [
        { location: ['items', 0, 'content'], message: '첫째' },
        { location: ['items', 0, 'content'], message: '둘째' },
        { location: ['items', 9, 'content'], message: '없는 행' },
        { location: ['body'], message: '위치 없음' },
      ],
      rowIndexOf,
    )
    // then: 첫 문구만 남는다
    expect(errors).toEqual({ 1: { content: '첫째' } })
  })

  // deal_code 위치는 무시한다.
  it('ignores a server location at deal_code', () => {
    // when: deal_code 위치 위반을 바꾼다
    const errors = applyServerErrors([{ location: ['items', 0, 'deal_code'], message: '옛 문구' }], rowIndexOf)
    // then: 오류가 없다
    expect(errors).toEqual({})
  })
})
