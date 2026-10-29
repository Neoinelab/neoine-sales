import { describe, expect, it } from 'vitest'
import { dateValueError } from '../../shared/model/dateText'
import { MAX_ROWS, applyServerErrors, emptyRow, firstMissingField, isBlank, isComplete, rowsToInputs, validateRows, type EntryRow } from './entryRows'

const TODAY = '2027-03-15'

/** 모두 채워진 행. 고르기 전의 글자(partnerText·dealText)와 고른 값(partnerCompany·dealCode)을 따로 둔다. */
function row(over: Partial<EntryRow> = {}): EntryRow {
  return {
    key: 'k',
    partnerText: '코어테크',
    partnerCompany: '코어테크',
    dealText: '대한제조 MFA 확대 [20270301-D002]',
    dealCode: '20270301-D002',
    meetingDate: '2027-03-10',
    content: '견적 전달',
    ...over,
  }
}

describe('emptyRow', () => {
  it('starts empty with the given date and a key of its own', () => {
    const a = emptyRow(TODAY)
    const b = emptyRow(TODAY)

    expect(a).toMatchObject({ partnerText: '', partnerCompany: '', dealText: '', dealCode: '', meetingDate: TODAY, content: '' })
    expect(a.key).not.toBe(b.key)
  })

  it('caps the rows at 50', () => {
    expect(MAX_ROWS).toBe(50)
  })
})

describe('isBlank', () => {
  it('ignores the date: an untouched row with the default date is blank', () => {
    expect(isBlank(emptyRow(TODAY))).toBe(true)
  })

  it.each([
    ['a typed partner', { partnerText: '코' }],
    ['a chosen partner', { partnerCompany: '코어테크' }],
    ['a typed deal', { dealText: 'ERP' }],
    ['a chosen deal', { dealCode: '20270301-D002' }],
    ['a content', { content: '내용' }],
  ])('is not blank with %s', (_name, over) => {
    expect(isBlank({ ...emptyRow(TODAY), ...over })).toBe(false)
  })

  it('treats a whitespace-only content as blank', () => {
    expect(isBlank({ ...emptyRow(TODAY), content: '  \n ' })).toBe(true)
  })
})

describe('isComplete and firstMissingField', () => {
  it('a row with partner, deal, a valid date and content is complete', () => {
    expect(isComplete(row())).toBe(true)
    expect(firstMissingField(row())).toBeNull()
  })

  it.each([
    ['partnerCompany', { partnerCompany: '' }],
    ['dealCode', { dealCode: '' }],
    ['meetingDate', { meetingDate: '' }],
    ['meetingDate', { meetingDate: '2027.03' }],
    ['meetingDate', { meetingDate: '2027.13.45' }],
    ['content', { content: '   ' }],
  ] as const)('reports %s when it is missing or wrong', (field, over) => {
    expect(isComplete(row(over))).toBe(false)
    expect(firstMissingField(row(over))).toBe(field)
  })

  it('reports the first missing field in the order partner, deal, date, content', () => {
    expect(firstMissingField(row({ partnerCompany: '', dealCode: '', content: '' }))).toBe('partnerCompany')
    expect(firstMissingField(row({ dealCode: '', content: '' }))).toBe('dealCode')
    expect(firstMissingField(row({ meetingDate: '2027.03', content: '' }))).toBe('meetingDate')
  })

  it('does not accept a typed-only partner or deal (nothing chosen from the list)', () => {
    expect(firstMissingField(row({ partnerCompany: '', partnerText: '코어' }))).toBe('partnerCompany')
    expect(firstMissingField(row({ dealCode: '', dealText: 'ERP' }))).toBe('dealCode')
  })
})

describe('validateRows', () => {
  it('skips blank rows and passes complete rows', () => {
    expect(validateRows([emptyRow(TODAY), row(), emptyRow(TODAY)])).toEqual({})
  })

  it('reports every problem of a partly filled row with the planned messages', () => {
    const errors = validateRows([row({ partnerCompany: '', partnerText: '코', dealCode: '', dealText: '', meetingDate: '', content: '' })])

    expect(errors).toEqual({
      0: {
        partnerCompany: '파트너를 선택하세요.',
        dealCode: 'Deal을 선택하세요.',
        meetingDate: '미팅 날짜를 입력하세요.',
        content: '미팅 내용을 입력하세요.',
      },
    })
  })

  it('uses the date message of the date rules for a wrong date', () => {
    const errors = validateRows([row({ meetingDate: '2027.03' })])

    expect(errors[0]).toEqual({ meetingDate: dateValueError('2027.03') })
  })

  it('keys the errors by the position in the given rows, not among the non-blank rows', () => {
    const errors = validateRows([emptyRow(TODAY), row(), row({ content: '' })])

    expect(Object.keys(errors)).toEqual(['2'])
    expect(errors[2]).toEqual({ content: '미팅 내용을 입력하세요.' })
  })

  it('does not look at the date of a blank row', () => {
    expect(validateRows([{ ...emptyRow(TODAY), meetingDate: '2027.03' }])).toEqual({})
  })
})

describe('rowsToInputs', () => {
  it('sends only the non-blank rows in order and remembers which row each input came from', () => {
    const result = rowsToInputs([emptyRow(TODAY), row({ content: '첫째' }), emptyRow(TODAY), row({ content: '둘째', meetingDate: '2027-03-11' })])

    expect(result.inputs).toEqual([
      { partnerCompany: '코어테크', dealCode: '20270301-D002', meetingDate: '2027-03-10', content: '첫째' },
      { partnerCompany: '코어테크', dealCode: '20270301-D002', meetingDate: '2027-03-11', content: '둘째' },
    ])
    expect(result.rowIndexOf).toEqual([1, 3])
  })

  it('returns nothing when every row is blank', () => {
    expect(rowsToInputs([emptyRow(TODAY), emptyRow(TODAY)])).toEqual({ inputs: [], rowIndexOf: [] })
  })
})

describe('applyServerErrors', () => {
  const rows = [emptyRow(TODAY), row(), emptyRow(TODAY), row()]
  const { rowIndexOf } = rowsToInputs(rows)

  it('maps the located violations of the sent items back to the screen rows and fields', () => {
    const errors = applyServerErrors(
      [
        { location: ['items', 0, 'deal_code'], message: '선택한 파트너와 연결된 Deal이 아닙니다.' },
        { location: ['items', 1, 'content'], message: '미팅 내용을 입력하세요.' },
        { location: ['items', 1, 'meeting_date'], message: '범위 문구' },
        { location: ['items', 0, 'partner_company'], message: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
      ],
      rowIndexOf,
    )

    expect(errors).toEqual({
      1: { dealCode: '선택한 파트너와 연결된 Deal이 아닙니다.', partnerCompany: '등록된 파트너 회사가 아닙니다. 목록에서 다시 선택하세요.' },
      3: { content: '미팅 내용을 입력하세요.', meetingDate: '범위 문구' },
    })
  })

  it('keeps the first message of a field and ignores locations it cannot place', () => {
    const errors = applyServerErrors(
      [
        { location: ['items', 0, 'content'], message: '첫째' },
        { location: ['items', 0, 'content'], message: '둘째' },
        { location: ['items', 9, 'content'], message: '없는 행' },
        { location: ['body'], message: '위치 없음' },
      ],
      rowIndexOf,
    )

    expect(errors).toEqual({ 1: { content: '첫째' } })
  })
})
