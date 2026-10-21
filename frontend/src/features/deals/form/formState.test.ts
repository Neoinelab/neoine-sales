import { describe, expect, it } from 'vitest'
import { AMOUNT_INPUT_MESSAGE } from '../../../shared/model/money'
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
    solution: { id: 3, name: 'SSO' },
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
    statusChangedAt: '2026-09-01T00:00:00+09:00',
    owner,
    customer: { ...contact(1, '한빛은행', '정민수'), kind: 'customer', title: '과장', email: 'a@b.co', phone: '02-1' },
    activePartner: contact(9, '에이원시스템', '표성호'),
    nextAction: null,
    lastUpdatedAt: '2026-10-01T00:00:00+09:00',
    risk: null,
    statusDays: 30,
    partnerHistory: [],
    ...over,
  }
}

describe('emptyForm (T-FORM-02, T-FORM-03)', () => {
  it('starts with the given owner, 기회발굴 and Pipeline and no partner', () => {
    const state = emptyForm(String(USER_ID.kim))
    expect(state.ownerId).toBe(String(USER_ID.kim))
    expect(state.statusKey).toBe('prospecting')
    expect(state.forecastKey).toBe('pipeline')
    expect(state.partner).toEqual(EMPTY_DRAFT)
    expect(isPartnerEntered(state.partner)).toBe(false)
  })

  it('AC-9 starts with no vendor and no solution as empty ids', () => {
    expect(emptyForm(String(USER_ID.kim))).toMatchObject({ vendorId: '', solutionId: '' })
  })

  it('AC-31 starts with an empty text for every BANT item', () => {
    expect(emptyForm(String(USER_ID.kim)).bant).toEqual({ budget: '', authority: '', need: '', timeline: '' })
  })
})

describe('validateForm (T-FORM-01)', () => {
  it('lists every missing required field with the contract messages', () => {
    const errors = validateForm({ ...emptyForm(''), revenueAmount: '', revenueDate: '' }, undefined)
    expect(errors.name).toBe('Deal Name을 입력하세요.')
    expect(errors.ownerId).toBe('Owner를 선택하세요.')
    expect(errors.customer?.company).toBe('고객 회사명을 입력하세요.')
    expect(errors.customer?.name).toBe('고객 담당자명을 입력하세요.')
    expect(errors.revenueAmount).toBe(AMOUNT_INPUT_MESSAGE)
    expect(errors.revenueDate).toBe('Expected Close를 입력하세요.')
    expect(errors.partner).toBeUndefined()
    expect(hasErrors(errors)).toBe(true)
  })

  it('AC-31 flags a BANT text over 50 characters at that item only', () => {
    const errors = validateForm(filled({ bant: { budget: '', authority: '가'.repeat(51), need: '', timeline: '' } }), undefined)

    expect(errors.bant).toEqual({ authority: 'Label 이름은 50자 이내로 입력하세요.' })
    expect(hasErrors(errors)).toBe(true)
  })

  it('AC-31 accepts exactly 50 characters and measures the trimmed text by code points', () => {
    const fifty = '😀'.repeat(50)

    expect(validateForm(filled({ bant: { budget: `  ${fifty}  `, authority: '', need: '', timeline: '' } }), undefined).bant).toBeUndefined()
    expect(validateForm(filled({ bant: { budget: '😀'.repeat(51), authority: '', need: '', timeline: '' } }), undefined).bant).toEqual({
      budget: 'Label 이름은 50자 이내로 입력하세요.',
    })
  })

  it('has no bant error key when every item is fine', () => {
    const errors = validateForm(filled(), undefined)

    expect(errors.bant).toBeUndefined()
    expect(hasErrors(errors)).toBe(false)
  })

  it('accepts a complete form', () => {
    expect(hasErrors(validateForm(filled(), undefined))).toBe(false)
  })

  it('treats a blank name as missing', () => {
    expect(validateForm(filled({ name: '   ' }), undefined).name).toBe('Deal Name을 입력하세요.')
  })

  it.each(['0', '-5', '1.5', 'abc'])('rejects the amount %s', (text) => {
    expect(validateForm(filled({ revenueAmount: text }), undefined).revenueAmount).toBe(AMOUNT_INPUT_MESSAGE)
  })

  it('requires Users and accepts zero or a positive integer', () => {
    expect(validateForm(filled({ users: '' }), undefined).users).toBe('Users를 입력하세요.')
    expect(validateForm(filled({ users: '-1' }), undefined).users).toBe('Users는 0 이상의 정수로 입력하세요.')
    expect(validateForm(filled({ users: '2.5' }), undefined).users).toBe('Users는 0 이상의 정수로 입력하세요.')
    expect(validateForm(filled({ users: '0' }), undefined).users).toBeUndefined()
    expect(validateForm(filled({ users: '10' }), undefined).users).toBeUndefined()
  })

  it('requires both company and name once a partner is started (T-FORM-05)', () => {
    const only = (patch: Partial<DealFormState['partner']>) =>
      validateForm(filled({ partner: { ...EMPTY_DRAFT, ...patch } }), undefined).partner
    expect(only({ company: '코어테크' })).toEqual({ company: '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.' })
    expect(only({ name: '민지훈' })).toEqual({ company: '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.' })
    expect(only({ title: '이사' })).toEqual({ company: '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.' })
    expect(only({ company: '코어테크', name: '민지훈' })).toBeUndefined()
  })

  it('checks the email format of the customer and the partner', () => {
    const errors = validateForm(
      filled({
        customer: { contactId: null, company: '한빛은행', name: '정민수', title: '', email: 'not-an-email', phone: null },
        partner: { contactId: null, company: '코어테크', name: '민지훈', title: '', email: 'bad@', phone: null },
      }),
      undefined,
    )
    expect(errors.customer?.email).toBe('이메일 형식이 올바르지 않습니다.')
    expect(errors.partner?.email).toBe('이메일 형식이 올바르지 않습니다.')
  })

  it('blocks saving while a resigned owner is still selected', () => {
    const resigned: UserRef = { id: USER_ID.old, name: '강퇴사', role: 'sales', status: 'resigned' }
    const errors = validateForm(filled({ ownerId: String(USER_ID.old) }), resigned)
    expect(errors.ownerId).toBe('퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.')
    expect(validateForm(filled({ ownerId: String(USER_ID.kim) }), resigned).ownerId).toBeUndefined()
  })
})

describe('toDealInput', () => {
  it('trims, converts numbers and uses null for empty optional values', () => {
    const input = toDealInput(
      filled({
        vendorId: '3',
        solutionId: '3',
        users: '20',
        customer: { contactId: 1, company: '한빛은행', name: '정민수', title: ' 과장 ', email: '', phone: '' },
        quoteSubmitted: 'YES',
        quoteDate: '2026-10-01',
      }),
      LABELS,
    )
    expect(input.name).toBe('새 Deal')
    expect(input).toMatchObject({ vendorId: 3, solutionId: 3 })
    expect(input.users).toBe(20)
    expect(input.revenueAmount).toBe(1_500_000_000)
    expect(input.customer).toEqual({ contactId: 1, company: '한빛은행', name: '정민수', title: '과장', email: null, phone: null })
    expect(input.partner).toBeNull()
    expect(input.quote).toEqual({ submitted: 'YES', submittedDate: '2026-10-01' })
    expect(input.poc).toEqual({ state: null, completedDate: null })
  })

  it('sends the owner, vendor and solution ids as numbers', () => {
    const input = toDealInput(filled({ ownerId: String(USER_ID.park), vendorId: '12', solutionId: '34' }), LABELS)

    expect(input.ownerId).toBe(USER_ID.park)
    expect(input.vendorId).toBe(12)
    expect(input.solutionId).toBe(34)
  })

  it('sends an empty vendor and solution as null', () => {
    const input = toDealInput(filled({ vendorId: '', solutionId: '' }), LABELS)

    expect(input.vendorId).toBeNull()
    expect(input.solutionId).toBeNull()
  })

  it('sends a vendor without a solution', () => {
    const input = toDealInput(filled({ vendorId: '3', solutionId: '' }), LABELS)

    expect(input.vendorId).toBe(3)
    expect(input.solutionId).toBeNull()
  })

  it('sends the partner only when it was entered', () => {
    const input = toDealInput(filled({ partner: { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' } }), LABELS)
    expect(input.partner).toMatchObject({ company: '코어테크', name: '민지훈', email: null })
  })
})

describe('toDealInput: BANT choices (AC-31)', () => {
  const bant = (over: Partial<DealFormState['bant']> = {}): DealFormState['bant'] => ({ budget: '', authority: '', need: '', timeline: '', ...over })

  it('sends null for a blank or blank-only item', () => {
    const input = toDealInput(filled({ bant: bant({ budget: '', need: '   ' }) }), LABELS)

    expect(input.bant).toEqual({ budget: null, authority: null, need: null, timeline: null })
  })

  it('sends the id of the label of that category with the same name, ignoring case and spaces', () => {
    const input = toDealInput(filled({ bant: bant({ budget: '  단독 예산 확보 ', authority: 'ceo 보고 완료' }) }), LABELS)

    expect(input.bant).toEqual({ budget: { id: 1 }, authority: { id: 3 }, need: null, timeline: null })
  })

  it('sends the trimmed name when the category has no such label, even if another category has it', () => {
    const input = toDealInput(filled({ bant: bant({ need: ' Shared ', timeline: '내후년 구매' }) }), LABELS)

    expect(input.bant).toEqual({ budget: null, authority: null, need: { name: 'Shared' }, timeline: { name: '내후년 구매' } })
  })

  it('resolves the same name per category on its own', () => {
    const input = toDealInput(filled({ bant: bant({ budget: 'shared', authority: 'SHARED' }) }), LABELS)

    expect(input.bant).toMatchObject({ budget: { id: 2 }, authority: { id: 4 } })
  })

  it('does not take a partial match as the same label', () => {
    const input = toDealInput(filled({ bant: bant({ budget: '단독' }) }), LABELS)

    expect(input.bant.budget).toEqual({ name: '단독' })
  })
})

describe('formFromDeal / toDealPatch (T-FORM-06)', () => {
  it('loads every field of an existing deal', () => {
    const state = formFromDeal(detail(), LABELS)
    expect(state).toMatchObject({
      name: '기존 Deal',
      ownerId: String(USER_ID.kim),
      users: '100',
      statusKey: 'introduction',
      forecastKey: 'best',
      revenueAmount: '300,000',
      revenueDate: '2027-03-01',
      quoteSubmitted: 'YES',
      procurement: '검토',
    })
    expect(state.customer).toMatchObject({ contactId: 1, company: '한빛은행', name: '정민수', title: '과장' })
    expect(state.partner).toMatchObject({ contactId: 9, company: '에이원시스템', name: '표성호' })
    expect(state.bant).toEqual({ budget: '단독 예산 확보', authority: '', need: '', timeline: '' })
    expect(state).toMatchObject({ vendorId: '3', solutionId: '3' })
  })

  it('loads a deal without vendor and solution as empty ids', () => {
    const state = formFromDeal(detail({ vendor: null, solution: null }), LABELS)

    expect(state).toMatchObject({ vendorId: '', solutionId: '' })
  })

  it('AC-11 patch carries the vendor and solution ids as they are in the form', () => {
    const original = detail()
    const state = { ...formFromDeal(original, LABELS), vendorId: '5', solutionId: '' }

    expect(toDealPatch(state, original, LABELS)).toMatchObject({ vendorId: 5, solutionId: null })
  })

  it('AC-8 patch keeps the original won amount when the shown thousands are unchanged', () => {
    const original = detail({ revenueAmount: 1_234_567 })
    const state = formFromDeal(original, LABELS)

    expect(state.revenueAmount).toBe('1,235')
    expect(toDealPatch(state, original, LABELS).revenueAmount).toBe(1_234_567)
  })

  it('AC-8 patch keeps the original won amount at the safe integer limit when untouched', () => {
    const original = detail({ revenueAmount: Number.MAX_SAFE_INTEGER })
    const state = formFromDeal(original, LABELS)

    expect(state.revenueAmount).toBe('9,007,199,254,741')
    expect(toDealPatch(state, original, LABELS).revenueAmount).toBe(Number.MAX_SAFE_INTEGER)
  })

  it('AC-6 patch sends the edited thousands multiplied to won', () => {
    const original = detail({ revenueAmount: 1_234_567 })
    const state = { ...formFromDeal(original, LABELS), revenueAmount: '2,000' }

    expect(toDealPatch(state, original, LABELS).revenueAmount).toBe(2_000_000)
  })

  it('AC-31 patch round-trips the current labels as their ids', () => {
    const original = detail()

    expect(toDealPatch(formFromDeal(original, LABELS), original, LABELS).bant).toEqual({ budget: { id: 1 }, authority: null, need: null, timeline: null })
  })

  it('AC-31 patch sends null for an item whose text was emptied and a name for a new text', () => {
    const original = detail()
    const state = { ...formFromDeal(original, LABELS), bant: { budget: '', authority: '', need: '', timeline: '내후년 구매' } }

    expect(toDealPatch(state, original, LABELS).bant).toEqual({ budget: null, authority: null, need: null, timeline: { name: '내후년 구매' } })
  })

  it('removes the active partner when its fields are cleared', () => {
    const original = detail()
    const state = { ...formFromDeal(original, LABELS), partner: EMPTY_DRAFT }
    expect(toDealPatch(state, original, LABELS).partner).toBeNull()
  })

  it('leaves the partner out when there was none and none is entered', () => {
    const original = detail({ activePartner: null })
    expect('partner' in toDealPatch(formFromDeal(original, LABELS), original, LABELS)).toBe(false)
  })

  it('sends the replacement partner as a draft', () => {
    const original = detail()
    const state = { ...formFromDeal(original, LABELS), partner: { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' } }
    expect(toDealPatch(state, original, LABELS).partner).toMatchObject({ contactId: null, company: '코어테크' })
  })
})

describe('replacedPartner (T-FORM-05 notice)', () => {
  const original = detail()

  it('is the active partner when a different one is entered', () => {
    const draft = { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' }
    expect(replacedPartner(original, draft)?.name).toBe('표성호')
  })

  it('is null for the same contact, for an empty draft and when there was no partner', () => {
    const same = { ...EMPTY_DRAFT, contactId: 9, company: '에이원시스템', name: '표성호', title: '이사' }
    expect(replacedPartner(original, same)).toBeNull()
    expect(replacedPartner(original, EMPTY_DRAFT)).toBeNull()
    expect(replacedPartner(detail({ activePartner: null }), { ...EMPTY_DRAFT, company: 'x', name: 'y' })).toBeNull()
    expect(replacedPartner(undefined, { ...EMPTY_DRAFT, company: 'x', name: 'y' })).toBeNull()
  })

  it('treats the same company and name typed by hand as the same partner', () => {
    const typed = { ...EMPTY_DRAFT, company: '에이원시스템', name: '표성호' }
    expect(replacedPartner(original, typed)).toBeNull()
  })
})
