import { describe, expect, it } from 'vitest'
import { AMOUNT_INPUT_MESSAGE, AMOUNT_TOO_LARGE_MESSAGE } from '../../../shared/model/money'
import type { BantLabel, Contact, DealDetail, UserRef } from '../../../shared/model/types'
import {
  EMPTY_DRAFT,
  emptyForm,
  formFromDeal,
  hasErrors,
  isPartnerEntered,
  replacedPartner,
  toDealInput,
  toDealPatch,
  validateForm,
  type DealFormState,
} from './formState'
import { USER_ID } from '../../../test/fake/seed/ids'

function filled(over: Partial<DealFormState> = {}): DealFormState {
  return {
    ...emptyForm(String(USER_ID.kim)),
    name: '새 Deal',
    customer: { contactId: null, company: '한빛은행', name: '정민수', title: ' 과장 ', email: 'a@b.co', phone: null },
    revenueAmount: '1,500,000',
    revenueDate: '2027-01-31',
    solution: 'ITDR',
    users: '10',
    ...over,
  }
}

const contact = (id: number, company: string, name: string): Contact => ({
  id,
  kind: 'partner',
  company,
  name,
  title: '',
  email: null,
  phone: null,
  createdAt: '2026-01-01T00:00:00+09:00',
  updatedAt: '2026-01-01T00:00:00+09:00',
})

const label = (id: number, category: BantLabel['category'], name: string): BantLabel => ({
  id,
  category,
  name,
  isDefault: true,
  createdBy: null,
  createdAt: '2026-01-01T00:00:00+09:00',
})

/** 구분마다 Label 하나 이상. 같은 이름이 다른 구분에도 있다(구분 안에서만 찾는지 확인용). */
const LABELS: readonly BantLabel[] = [
  label(1, 'budget', '단독 예산 확보'),
  label(2, 'budget', 'Shared'),
  label(3, 'authority', 'CEO 보고 완료'),
  label(4, 'authority', 'Shared'),
  label(5, 'need', '모름'),
  label(6, 'timeline', '금년 구매'),
]

const owner: UserRef = { id: USER_ID.kim, name: '김영업', role: 'sales', status: 'active' }

function detail(over: Partial<DealDetail> = {}): DealDetail {
  return {
    code: '20261015-D001',
    name: '기존 Deal',
    ownerId: USER_ID.kim,
    vendor: { id: 3, name: 'Okta' },
    solution: 'SSO',
    users: 100,
    statusKey: 'introduction',
    forecastKey: 'best',
    revenueAmount: 300_000_000,
    revenueDate: '2027-03-01',
    customerContactId: 1,
    partnerLinks: [],
    quote: { submitted: 'YES', submittedDate: '2026-10-01' },
    poc: { state: null, completedDate: null },
    procurement: '검토',
    bant: { budget: 1, authority: null, need: null, timeline: null },
    createdAt: '2026-09-01T00:00:00+09:00',
    updatedAt: '2026-10-01T00:00:00+09:00',
    statusChangedOn: '2026-09-01',
    owner,
    customer: { ...contact(1, '한빛은행', '정민수'), kind: 'customer', title: '과장', email: 'a@b.co', phone: '02-1' },
    activePartner: contact(9, '에이원시스템', '표성호'),
    licenseContractCount: 0,
    hasIssuedLicenseContract: false,
    nextAction: null,
    lastUpdatedOn: '2026-10-01',
    risk: null,
    statusDays: 30,
    partnerHistory: [],
    ...over,
  }
}

describe('emptyForm (T-FORM-02, T-FORM-03)', () => {
  // 빈 폼은 주어진 Owner, 기회발굴, Pipeline으로 시작하고 파트너가 없다.
  // 테스트 코드: DE-073
  it('starts with the given owner, 기회발굴 and Pipeline and no partner', () => {
    // when: emptyForm에 Owner를 주고 만든다.
    const state = emptyForm(String(USER_ID.kim))
    // then: Owner·Status·Forecast가 기본값이고 파트너 칸이 비어 있다.
    expect(state.ownerId).toBe(String(USER_ID.kim))
    expect(state.statusKey).toBe('prospecting')
    expect(state.forecastKey).toBe('pipeline')
    expect(state.partner).toEqual(EMPTY_DRAFT)
    expect(isPartnerEntered(state.partner)).toBe(false)
  })

  // Vendor 없음, 빈 Solution으로 시작한다.
  // 테스트 코드: DE-073
  it('starts with no vendor and an empty solution text', () => {
    // when: emptyForm을 만든다.
    const state = emptyForm(String(USER_ID.kim))

    // then: vendorId가 비고 solution이 ''다.
    expect(state).toMatchObject({ vendorId: '', solution: '' })
    expect(state).not.toHaveProperty('solutionId')
  })

  // BANT 칸 네 개 모두 빈 텍스트로 시작한다.
  // 테스트 코드: DE-073
  it('starts with an empty text for every BANT item', () => {
    // when: emptyForm을 만든다.
    const result = emptyForm(String(USER_ID.kim)).bant
    // then: 네 BANT 칸이 ''다.
    expect(result).toEqual({ budget: '', authority: '', need: '', timeline: '' })
  })
})

describe('validateForm (T-FORM-01)', () => {
  // 빈 폼은 필수 항목을 계약 문구로 모두 알린다.
  // 테스트 코드: DE-077
  it('lists every missing required field with the contract messages', () => {
    // when: validateForm을 호출한다 (전제: 빈 폼이다)
    const errors = validateForm({ ...emptyForm(''), revenueAmount: '', revenueDate: '' }, undefined)
    // then: 필수 항목마다 문구가 있다.
    expect(errors.name).toBe('Deal Name을 입력하세요.')
    expect(errors.ownerId).toBe('Owner를 선택하세요.')
    expect(errors.solution).toBe('Solution을 입력하세요.')
    expect(errors.customer?.company).toBe('고객 회사명을 입력하세요.')
    expect(errors.customer?.name).toBe('고객 담당자명을 입력하세요.')
    expect(errors.revenueAmount).toBe(AMOUNT_INPUT_MESSAGE)
    expect(errors.revenueDate).toBe('Expected Close를 입력하세요.')
    expect(errors.partner).toBeUndefined()
    expect(hasErrors(errors)).toBe(true)
  })

  // 비었거나 공백뿐인 Solution은 필수 문구다.
  // 테스트 코드: DE-087
  it.each(['', '   ', '\t'])('Q1 requires a non-blank solution text: "%s"', (solution) => {
    // when: validateForm을 호출한다 (전제: Solution이 ''·공백·탭이다)
    const errors = validateForm(filled({ solution }), undefined)

    // then: 'Solution을 입력하세요.'다.
    expect(errors.solution).toBe('Solution을 입력하세요.')
    expect(hasErrors(errors)).toBe(true)
  })

  // Vendor 없는 Solution 텍스트는 통과하고 길이는 서버가 판정한다.
  // 테스트 코드: DE-086
  it('Q1 accepts a solution text without a vendor and lets the server judge the length', () => {
    // when: validateForm을 호출한다 (전제: Vendor 없이 긴 Solution이다)
    const result1 = validateForm(filled({ vendorId: '', solution: 'ITDR' }), undefined).solution
    const result2 = validateForm(filled({ solution: 'a'.repeat(201) }), undefined).solution
    // then: Solution 오류가 없다.
    expect(result1).toBeUndefined()
    expect(result2).toBeUndefined()
  })

  // 50자를 넘는 BANT 텍스트는 그 칸에만 오류를 낸다.
  // 테스트 코드: DE-095
  it('flags a BANT text over 50 characters at that item only', () => {
    // when: validateForm을 호출한다 (전제: 한 BANT 칸이 51자다)
    const errors = validateForm(filled({ bant: { budget: '', authority: '가'.repeat(51), need: '', timeline: '' } }), undefined)

    // then: 그 칸 키에만 오류가 있다.
    expect(errors.bant).toEqual({ authority: 'Label 이름은 50자 이내로 입력하세요.' })
    expect(hasErrors(errors)).toBe(true)
  })

  // 정확히 50자는 허용하고 앞뒤 공백을 지운 코드 포인트로 센다.
  // 테스트 코드: DE-095
  it('accepts exactly 50 characters and measures the trimmed text by code points', () => {
    // when: validateForm을 호출한다 (전제: 50자 텍스트와 이모지 텍스트다)
    const fifty = '😀'.repeat(50)

    // then: BANT 오류가 없다.
    expect(validateForm(filled({ bant: { budget: `  ${fifty}  `, authority: '', need: '', timeline: '' } }), undefined).bant).toBeUndefined()
    expect(validateForm(filled({ bant: { budget: '😀'.repeat(51), authority: '', need: '', timeline: '' } }), undefined).bant).toEqual({
      budget: 'Label 이름은 50자 이내로 입력하세요.',
    })
  })

  // BANT 칸이 모두 정상이면 bant 오류 키가 없다.
  it('has no bant error key when every item is fine', () => {
    // when: validateForm을 호출한다 (전제: 정상 폼이다)
    const errors = validateForm(filled(), undefined)

    // then: bant 오류 키가 없다.
    expect(errors.bant).toBeUndefined()
    expect(hasErrors(errors)).toBe(false)
  })

  // 완성된 폼은 오류가 없다.
  it('accepts a complete form', () => {
    // when: validateForm을 호출한다 (전제: 완성된 폼이다)
    const result = hasErrors(validateForm(filled(), undefined))
    // then: 오류가 없다.
    expect(result).toBe(false)
  })

  // 비어 있는 Expected Close는 필수 문구, 틀린 날짜는 날짜 문구다.
  // 테스트 코드: DE-080
  it('keeps the required message for an empty Expected Close and refuses a wrong date text with the date message', () => {
    // when: validateForm을 호출한다 (전제: 빈 날짜와 틀린 날짜 텍스트다)
    const result1 = validateForm(filled({ revenueDate: '' }), undefined).revenueDate
    const result2 = validateForm(filled({ revenueDate: '2027.13.01' }), undefined).revenueDate
    const result3 = validateForm(filled({ revenueDate: '2027.1' }), undefined).revenueDate
    const result4 = validateForm(filled({ revenueDate: '3000-01-01' }), undefined).revenueDate
    // then: 각각 필수 문구·날짜 문구다.
    expect(result1).toBe('Expected Close를 입력하세요.')
    expect(result2).toBe('없는 날짜입니다.')
    expect(result3).toBe('날짜를 yyyymmdd 형식으로 입력하세요.')
    expect(result4).toBe('1900.01.01부터 2999.12.31 사이로 입력하세요.')
  })

  // 틀린 견적·POC 날짜는 거절하고 비어 있거나 올바른 날짜는 허용한다.
  // 테스트 코드: DE-080
  it('refuses a wrong quote or POC date text but accepts empty and valid dates', () => {
    // when: validateForm을 호출한다 (전제: 틀린·빈·올바른 날짜 텍스트다)
    const result = validateForm(filled({ quoteDate: '2027.1.' , pocDate: '2027.02.30' }), undefined)
    // then: 틀린 것만 오류다.
    expect(result).toMatchObject({
      quoteDate: '날짜를 yyyymmdd 형식으로 입력하세요.',
      pocDate: '없는 날짜입니다.',
    })
    const ok = validateForm(filled({ quoteDate: '', pocDate: '2027-03-04' }), undefined)
    expect(ok.quoteDate).toBeUndefined()
    expect(ok.pocDate).toBeUndefined()
  })

  // 공백뿐인 이름은 누락으로 본다.
  // 테스트 코드: DE-077
  it('treats a blank name as missing', () => {
    // when: validateForm을 호출한다 (전제: 이름이 공백뿐이다)
    const result = validateForm(filled({ name: '   ' }), undefined).name
    // then: 'Deal Name을 입력하세요.'다.
    expect(result).toBe('Deal Name을 입력하세요.')
  })

  // 0·음수·소수·문자 금액은 거절한다.
  // 테스트 코드: DE-078
  it.each(['0', '-5', '1.5', 'abc'])('rejects the amount %s', (text) => {
    // when: validateForm을 호출한다 (전제: 금액 텍스트가 0, -5, 1.5, abc다)
    const result = validateForm(filled({ revenueAmount: text }), undefined).revenueAmount
    // then: 금액 입력 문구다.
    expect(result).toBe(AMOUNT_INPUT_MESSAGE)
  })

  // 2^53은 거절하고 2^53-1은 허용한다.
  // 테스트 코드: DE-078
  it('rejects 2^53 and accepts 2^53-1', () => {
    // when: validateForm을 호출한다 (전제: 금액이 2^53, 2^53-1이다)
    const result1 = validateForm(filled({ revenueAmount: '9,007,199,254,740,992' }), undefined).revenueAmount
    const result2 = validateForm(filled({ revenueAmount: '9,007,199,254,740,991' }), undefined).revenueAmount
    // then: 2^53만 상한 초과 문구다.
    expect(result1).toBe(AMOUNT_TOO_LARGE_MESSAGE)
    expect(result2).toBeUndefined()
  })

  // Users count는 필수이고 0 이상의 정수만 허용한다.
  // 테스트 코드: DE-079
  it('requires Users count and accepts zero or a positive integer', () => {
    // when: validateForm을 호출한다 (전제: 빈 값·음수·0·양수다)
    const result1 = validateForm(filled({ users: '' }), undefined).users
    const result2 = validateForm(filled({ users: '-1' }), undefined).users
    const result3 = validateForm(filled({ users: '2.5' }), undefined).users
    const result4 = validateForm(filled({ users: '0' }), undefined).users
    const result5 = validateForm(filled({ users: '10' }), undefined).users
    // then: 빈 값은 필수 문구, 음수는 정수 문구, 0·양수는 통과다.
    expect(result1).toBe('Users count를 입력하세요.')
    expect(result2).toBe('Users count는 0 이상의 정수로 입력하세요.')
    expect(result3).toBe('Users count는 0 이상의 정수로 입력하세요.')
    expect(result4).toBeUndefined()
    expect(result5).toBeUndefined()
  })

  // 파트너 입력을 시작하면 회사명·담당자명이 모두 필요하다.
  // 테스트 코드: DE-081
  it('requires both company and name once a partner is started (T-FORM-05)', () => {
    // when: validateForm을 호출한다 (전제: 파트너 회사명만 있다)
    const only = (patch: Partial<DealFormState['partner']>) =>
      validateForm(filled({ partner: { ...EMPTY_DRAFT, ...patch } }), undefined).partner
    // then: 파트너 반쪽 입력 문구다.
    expect(only({ company: '코어테크' })).toEqual({ company: '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.' })
    expect(only({ name: '민지훈' })).toEqual({ company: '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.' })
    expect(only({ title: '이사' })).toEqual({ company: '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.' })
    expect(only({ company: '코어테크', name: '민지훈' })).toBeUndefined()
  })

  // 고객·파트너 이메일 형식을 검사한다.
  // 테스트 코드: DE-082
  it('checks the email format of the customer and the partner', () => {
    // when: validateForm을 호출한다 (전제: 틀린 이메일이다)
    const errors = validateForm(
      filled({
        customer: { contactId: null, company: '한빛은행', name: '정민수', title: '', email: 'not-an-email', phone: null },
        partner: { contactId: null, company: '코어테크', name: '민지훈', title: '', email: 'bad@', phone: null },
      }),
      undefined,
    )
    // then: 이메일 형식 문구다.
    expect(errors.customer?.email).toBe('이메일 형식이 올바르지 않습니다.')
    expect(errors.partner?.email).toBe('이메일 형식이 올바르지 않습니다.')
  })

  // 퇴사한 Owner가 선택된 채로는 저장을 막는다.
  // 테스트 코드: DE-102
  it('blocks saving while a resigned owner is still selected', () => {
    // given: Owner가 퇴사자다.
    const resigned: UserRef = { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' }
    // when: validateForm을 호출한다.
    const errors = validateForm(filled({ ownerId: String(USER_ID.old) }), resigned)
    // then: 퇴사 문구 오류다.
    expect(errors.ownerId).toBe('퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.')
    expect(validateForm(filled({ ownerId: String(USER_ID.kim) }), resigned).ownerId).toBeUndefined()
  })
})

describe('toDealInput', () => {
  // 공백 제거, 숫자 변환, 빈 선택값 null로 요청 값을 만든다.
  // 테스트 코드: DE-110
  it('trims, converts numbers and uses null for empty optional values', () => {
    // when: toDealInput을 호출한다 (전제: 공백·문자 숫자·빈 선택값이 든 폼이다)
    const input = toDealInput(
      filled({
        vendorId: '3',
        solution: ' SSO ',
        users: '20',
        customer: { contactId: 1, company: '한빛은행', name: '정민수', title: ' 과장 ', email: '', phone: '' },
        quoteSubmitted: 'YES',
        quoteDate: '2026-10-01',
      }),
      LABELS,
    )
    // then: 트림된 문자열, 숫자, null이다.
    expect(input.name).toBe('새 Deal')
    expect(input).toMatchObject({ vendorId: 3, solution: 'SSO' })
    expect(input).not.toHaveProperty('solutionId')
    expect(input.users).toBe(20)
    expect(input.revenueAmount).toBe(1_500_000)
    expect(input.customer).toEqual({ contactId: 1, company: '한빛은행', name: '정민수', title: '과장', email: null, phone: null })
    expect(input.partner).toBeNull()
    expect(input.quote).toEqual({ submitted: 'YES', submittedDate: '2026-10-01' })
    expect(input.poc).toEqual({ state: null, completedDate: null })
  })

  // Owner·Vendor id는 숫자로 보낸다.
  // 테스트 코드: DE-110
  it('sends the owner and vendor ids as numbers', () => {
    // when: toDealInput을 호출한다 (전제: 문자열 id가 든 폼이다)
    const input = toDealInput(filled({ ownerId: String(USER_ID.park), vendorId: '12' }), LABELS)

    // then: ownerId·vendorId가 number다.
    expect(input.ownerId).toBe(USER_ID.park)
    expect(input.vendorId).toBe(12)
  })

  // 빈 Vendor는 null, Solution은 공백을 지워 보낸다.
  // 테스트 코드: DE-110
  it('sends an empty vendor as null and the solution text trimmed', () => {
    // when: toDealInput을 호출한다 (전제: Vendor 없음, Solution ' ITDR '다)
    const input = toDealInput(filled({ vendorId: '', solution: '  ITDR  ' }), LABELS)

    // then: vendorId null, solution 'ITDR'이다.
    expect(input.vendorId).toBeNull()
    expect(input.solution).toBe('ITDR')
  })

  // Vendor와 독립인 Solution 텍스트를 함께 보낸다.
  // 테스트 코드: DE-110
  it('sends a vendor together with an independent solution text', () => {
    // when: toDealInput을 호출한다 (전제: Vendor와 Solution이 있다)
    const input = toDealInput(filled({ vendorId: '3', solution: 'MFA' }), LABELS)

    // then: 둘 다 요청에 있다.
    expect(input.vendorId).toBe(3)
    expect(input.solution).toBe('MFA')
  })

  // 파트너는 입력했을 때만 보낸다.
  // 테스트 코드: DE-110
  it('sends the partner only when it was entered', () => {
    // when: toDealInput을 호출한다 (전제: 파트너가 있는 폼, 없는 폼이다)
    const input = toDealInput(filled({ partner: { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' } }), LABELS)
    // then: 입력했을 때만 partner가 있고 아니면 null이다.
    expect(input.partner).toMatchObject({ company: '코어테크', name: '민지훈', email: null })
  })
})

describe('toDealInput: BANT choices', () => {
  const bant = (over: Partial<DealFormState['bant']> = {}): DealFormState['bant'] => ({ budget: '', authority: '', need: '', timeline: '', ...over })

  // 빈 칸·공백뿐인 BANT는 null로 보낸다.
  // 테스트 코드: DE-096
  it('sends null for a blank or blank-only item', () => {
    // when: toDealInput을 호출한다 (전제: BANT 칸이 비었거나 공백뿐이다)
    const input = toDealInput(filled({ bant: bant({ budget: '', need: '   ' }) }), LABELS)

    // then: 해당 구분이 null이다.
    expect(input.bant).toEqual({ budget: null, authority: null, need: null, timeline: null })
  })

  // 같은 구분에 이름이 같은 Label이 있으면 대소문자·공백을 무시하고 id로 보낸다.
  // 테스트 코드: DE-096
  it('sends the id of the label of that category with the same name, ignoring case and spaces', () => {
    // when: toDealInput을 호출한다 (전제: 구분에 Label이 있다)
    const input = toDealInput(filled({ bant: bant({ budget: '  단독 예산 확보 ', authority: 'ceo 보고 완료' }) }), LABELS)

    // then: {id}다.
    expect(input.bant).toEqual({ budget: { id: 1 }, authority: { id: 3 }, need: null, timeline: null })
  })

  // 그 구분에 없는 이름은 다른 구분에 있어도 트림한 {name}으로 보낸다.
  // 테스트 코드: DE-096
  it('sends the trimmed name when the category has no such label, even if another category has it', () => {
    // when: toDealInput을 호출한다 (전제: 다른 구분에만 있는 이름이다)
    const input = toDealInput(filled({ bant: bant({ need: ' Shared ', timeline: '내후년 구매' }) }), LABELS)

    // then: {name}이다.
    expect(input.bant).toEqual({ budget: null, authority: null, need: { name: 'Shared' }, timeline: { name: '내후년 구매' } })
  })

  // 같은 이름도 구분마다 따로 해석한다.
  // 테스트 코드: DE-096
  it('resolves the same name per category on its own', () => {
    // when: toDealInput을 호출한다 (전제: 두 구분에 같은 이름이다)
    const input = toDealInput(filled({ bant: bant({ budget: 'shared', authority: 'SHARED' }) }), LABELS)

    // then: 구분별로 id 또는 name이다.
    expect(input.bant).toMatchObject({ budget: { id: 2 }, authority: { id: 4 } })
  })

  // 부분 일치는 같은 Label로 보지 않는다.
  // 테스트 코드: DE-096
  it('does not take a partial match as the same label', () => {
    // when: toDealInput을 호출한다 (전제: Label의 일부만 입력했다)
    const input = toDealInput(filled({ bant: bant({ budget: '단독' }) }), LABELS)

    // then: {name}으로 보낸다.
    expect(input.bant.budget).toEqual({ name: '단독' })
  })
})

describe('formFromDeal / toDealPatch (T-FORM-06)', () => {
  // 기존 Deal의 모든 필드를 폼으로 읽는다.
  // 테스트 코드: DE-100
  it('loads every field of an existing deal', () => {
    // when: formFromDeal을 호출한다 (전제: Deal 상세가 있다)
    const state = formFromDeal(detail(), LABELS)
    // then: 모든 칸이 현재 값이다.
    expect(state).toMatchObject({
      name: '기존 Deal',
      ownerId: String(USER_ID.kim),
      users: '100',
      statusKey: 'introduction',
      forecastKey: 'best',
      revenueAmount: '300,000,000',
      revenueDate: '2027-03-01',
      quoteSubmitted: 'YES',
      procurement: '검토',
    })
    expect(state.customer).toMatchObject({ contactId: 1, company: '한빛은행', name: '정민수', title: '과장' })
    expect(state.partner).toMatchObject({ contactId: 9, company: '에이원시스템', name: '표성호' })
    expect(state.bant).toEqual({ budget: '단독 예산 확보', authority: '', need: '', timeline: '' })
    expect(state).toMatchObject({ vendorId: '3', solution: 'SSO' })
  })

  // Solution을 복사하고 Vendor가 없으면 빈 id로 읽는다.
  // 테스트 코드: DE-100
  it('form from deal copies the solution text and loads no vendor as an empty id', () => {
    // when: formFromDeal을 호출한다 (전제: Vendor 없는 Deal이다)
    const state = formFromDeal(detail({ vendor: null, solution: 'ITDR' }), LABELS)

    // then: vendorId가 ''이고 solution이 복사된다.
    expect(state).toMatchObject({ vendorId: '', solution: 'ITDR' })
  })

  // 레거시 빈 Solution은 빈 칸으로 읽는다.
  // 테스트 코드: DE-100
  it('loads a legacy empty solution as an empty text (the form then asks for one)', () => {
    // when: formFromDeal을 호출한다 (전제: Solution이 ''인 Deal이다)
    const result = formFromDeal(detail({ solution: '' }), LABELS).solution
    // then: solution 칸이 ''다.
    expect(result).toBe('')
  })

  // 수정 요청에 폼의 Vendor id와 Solution을 그대로 싣는다.
  // 테스트 코드: DE-110
  it('patch carries the vendor id and the solution text as they are in the form', () => {
    // given: Vendor·Solution이 든 폼이다.
    const original = detail()
    const state = { ...formFromDeal(original, LABELS), vendorId: '5', solution: ' MFA ' }

    // when: toDealPatch를 호출한다.
    const patch = toDealPatch(state, original, LABELS)

    // then: vendorId·solution이 patch에 있다.
    expect(patch).toMatchObject({ vendorId: 5, solution: 'MFA' })
    expect(patch).not.toHaveProperty('solutionId')
  })

  // Vendor만 바꿔도 바뀌지 않은 Solution을 다시 보낸다.
  // 테스트 코드: DE-110
  it('patch resends the unchanged solution text when only the vendor changed', () => {
    // given: Vendor만 바꾼 폼이다.
    const original = detail()
    // when: toDealPatch를 호출한다.
    const state = { ...formFromDeal(original, LABELS), vendorId: '5' }

    // then: solution도 patch에 있다.
    expect(toDealPatch(state, original, LABELS).solution).toBe('SSO')
  })

  // 저장된 금액을 콤마로 보이고 patch에서는 그대로 유지한다.
  // 테스트 코드: DE-109
  it('form shows the stored won amount with commas and keeps it unchanged in the patch', () => {
    // given: 금액이 든 Deal이다.
    const original = detail({ revenueAmount: 1_234_567 })
    // when: formFromDeal·toDealPatch를 호출한다.
    const state = formFromDeal(original, LABELS)

    // then: 폼은 콤마 표기, patch 금액은 같은 값이다.
    expect(state.revenueAmount).toBe('1,234,567')
    expect(toDealPatch(state, original, LABELS).revenueAmount).toBe(1_234_567)
  })

  // 안전 정수 상한을 정확히 유지한다.
  // 테스트 코드: DE-078
  it('form keeps the safe integer limit exactly', () => {
    // given: 금액이 2^53-1인 Deal이다.
    const original = detail({ revenueAmount: Number.MAX_SAFE_INTEGER })
    // when: formFromDeal을 호출한다.
    const state = formFromDeal(original, LABELS)

    // then: 금액 칸이 정확한 상한 표기다.
    expect(state.revenueAmount).toBe('9,007,199,254,740,991')
    expect(toDealPatch(state, original, LABELS).revenueAmount).toBe(Number.MAX_SAFE_INTEGER)
  })

  // 고친 금액을 입력한 대로 보낸다.
  // 테스트 코드: DE-110
  it('patch sends the edited won amount as typed', () => {
    // given: 금액을 고친 폼이다.
    const original = detail({ revenueAmount: 1_234_567 })
    // when: toDealPatch를 호출한다.
    const state = { ...formFromDeal(original, LABELS), revenueAmount: '2,000' }

    // then: patch 금액이 입력값이다.
    expect(toDealPatch(state, original, LABELS).revenueAmount).toBe(2_000)
  })

  // 건드리지 않은 300원 금액을 유지한다.
  // 테스트 코드: DE-109
  it('patch keeps a 300 won amount that was not touched', () => {
    // given: 금액 300원인 Deal이다.
    const original = detail({ revenueAmount: 300 })
    // when: toDealPatch를 호출한다.
    const state = formFromDeal(original, LABELS)

    // then: 금액이 300이다.
    expect(state.revenueAmount).toBe('300')
    expect(toDealPatch(state, original, LABELS).revenueAmount).toBe(300)
  })

  // 현재 Label을 id로 그대로 돌려보낸다.
  // 테스트 코드: DE-098
  it('patch round-trips the current labels as their ids', () => {
    // given: Label이 있는 Deal을 폼으로 읽었다
    const original = detail()

    // when: toDealPatch를 호출한다
    const result = toDealPatch(formFromDeal(original, LABELS), original, LABELS).bant
    // then: 각 구분이 원래 {id}다.
    expect(result).toEqual({ budget: { id: 1 }, authority: null, need: null, timeline: null })
  })

  // 비운 칸은 null, 새 텍스트는 이름으로 보낸다.
  // 테스트 코드: DE-098
  it('patch sends null for an item whose text was emptied and a name for a new text', () => {
    // given: 칸을 비우고 다른 칸에 새 텍스트를 입력했다.
    const original = detail()
    // when: toDealPatch를 호출한다.
    const state = { ...formFromDeal(original, LABELS), bant: { budget: '', authority: '', need: '', timeline: '내후년 구매' } }

    // then: null과 {name}이다.
    expect(toDealPatch(state, original, LABELS).bant).toEqual({ budget: null, authority: null, need: null, timeline: { name: '내후년 구매' } })
  })

  // 파트너 칸을 비우면 활성 파트너를 제거(null)로 보낸다.
  // 테스트 코드: DE-110
  it('removes the active partner when its fields are cleared', () => {
    // given: 활성 파트너가 있는 Deal의 폼에서 칸을 비웠다.
    const original = detail()
    // when: toDealPatch를 호출한다.
    const state = { ...formFromDeal(original, LABELS), partner: EMPTY_DRAFT }
    // then: partner가 null이다.
    expect(toDealPatch(state, original, LABELS).partner).toBeNull()
  })

  // 파트너가 없고 입력도 없으면 partner 키를 보내지 않는다.
  // 테스트 코드: DE-110
  it('leaves the partner out when there was none and none is entered', () => {
    // given: 파트너가 없던 Deal이다
    const original = detail({ activePartner: null })

    // when: toDealPatch를 호출한다
    const result = 'partner' in toDealPatch(formFromDeal(original, LABELS), original, LABELS)
    // then: partner 키가 없다.
    expect(result).toBe(false)
  })

  // 교체 파트너는 연락처 입력으로 보낸다.
  // 테스트 코드: DE-101
  it('sends the replacement partner as a draft', () => {
    // given: 다른 파트너를 입력했다.
    const original = detail()
    // when: toDealPatch를 호출한다.
    const state = { ...formFromDeal(original, LABELS), partner: { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' } }
    // then: partner가 입력값이다.
    expect(toDealPatch(state, original, LABELS).partner).toMatchObject({ contactId: null, company: '코어테크' })
  })
})

describe('replacedPartner (T-FORM-05 notice)', () => {
  const original = detail()

  // 다른 파트너를 입력하면 교체 대상은 활성 파트너다.
  // 테스트 코드: DE-101
  it('is the active partner when a different one is entered', () => {
    // given: 다른 파트너를 입력했다
    const draft = { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' }

    // when: replacedPartner를 호출한다
    const result = replacedPartner(original, draft)?.name
    // then: 기존 활성 파트너다.
    expect(result).toBe('표성호')
  })

  // 같은 연락처·빈 입력·파트너 없음이면 교체가 아니다.
  // 테스트 코드: DE-101
  it('is null for the same contact, for an empty draft and when there was no partner', () => {
    // given: 같은 연락처를 골랐다
    const same = { ...EMPTY_DRAFT, contactId: 9, company: '에이원시스템', name: '표성호', title: '이사' }
    // when: replacedPartner를 호출한다
    const replaced = replacedPartner(original, same)
    // then: null이다.
    expect(replaced).toBeNull()
    expect(replacedPartner(original, EMPTY_DRAFT)).toBeNull()
    expect(replacedPartner(detail({ activePartner: null }), { ...EMPTY_DRAFT, company: 'x', name: 'y' })).toBeNull()
    expect(replacedPartner(undefined, { ...EMPTY_DRAFT, company: 'x', name: 'y' })).toBeNull()
  })

  // 회사명·담당자명을 대소문자 무시로 같게 입력하면 같은 파트너다.
  // 테스트 코드: DE-101
  it('treats the same company and name typed by hand as the same partner', () => {
    // given: 같은 이름을 직접 입력했다
    const typed = { ...EMPTY_DRAFT, company: '에이원시스템', name: '표성호' }

    // when: replacedPartner를 호출한다
    const result = replacedPartner(original, typed)
    // then: null이다.
    expect(result).toBeNull()
  })
})
