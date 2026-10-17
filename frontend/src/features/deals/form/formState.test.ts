import { describe, expect, it } from 'vitest'
import type { Contact, DealDetail, UserRef } from '../../../shared/model/types'
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

function filled(over: Partial<DealFormState> = {}): DealFormState {
  return {
    ...emptyForm('u-kim'),
    name: '새 Deal',
    customer: { contactId: null, company: '한빛은행', name: '정민수', title: ' 과장 ', email: 'a@b.co', phone: null },
    revenueAmount: '1,500,000',
    revenueDate: '2027-01-31',
    ...over,
  }
}

const contact = (id: string, company: string, name: string): Contact => ({
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

const owner: UserRef = { id: 'u-kim', name: '김영업', role: 'sales', status: 'active' }

function detail(over: Partial<DealDetail> = {}): DealDetail {
  return {
    code: '20261015-D001',
    name: '기존 Deal',
    ownerId: 'u-kim',
    vendor: 'Okta',
    solution: 'SSO',
    users: 100,
    statusKey: 'introduction',
    forecastKey: 'best',
    revenueAmount: 300_000_000,
    revenueDate: '2027-03-01',
    customerContactId: 'ct-1',
    partnerLinks: [],
    quote: { submitted: 'YES', submittedDate: '2026-10-01' },
    poc: { state: null, completedDate: null },
    procurement: '검토',
    bant: { budget: 'lb-1', authority: null, need: null, timeline: null },
    createdAt: '2026-09-01T00:00:00+09:00',
    updatedAt: '2026-10-01T00:00:00+09:00',
    statusChangedAt: '2026-09-01T00:00:00+09:00',
    owner,
    customer: { ...contact('ct-1', '한빛은행', '정민수'), kind: 'customer', title: '과장', email: 'a@b.co', phone: '02-1' },
    activePartner: contact('ct-9', '에이원시스템', '표성호'),
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
    const state = emptyForm('u-kim')
    expect(state.ownerId).toBe('u-kim')
    expect(state.statusKey).toBe('prospecting')
    expect(state.forecastKey).toBe('pipeline')
    expect(state.partner).toEqual(EMPTY_DRAFT)
    expect(isPartnerEntered(state.partner)).toBe(false)
  })
})

describe('validateForm (T-FORM-01)', () => {
  it('lists every missing required field with the contract messages', () => {
    const errors = validateForm({ ...emptyForm(''), revenueAmount: '', revenueDate: '' }, undefined)
    expect(errors.name).toBe('Deal Name을 입력하세요.')
    expect(errors.ownerId).toBe('Owner를 선택하세요.')
    expect(errors.customer?.company).toBe('고객 회사명을 입력하세요.')
    expect(errors.customer?.name).toBe('고객 담당자명을 입력하세요.')
    expect(errors.revenueAmount).toBe('매출금액은 1원 이상의 정수로 입력하세요.')
    expect(errors.revenueDate).toBe('Expected Close를 입력하세요.')
    expect(errors.partner).toBeUndefined()
    expect(hasErrors(errors)).toBe(true)
  })

  it('accepts a complete form', () => {
    expect(hasErrors(validateForm(filled(), undefined))).toBe(false)
  })

  it('treats a blank name as missing', () => {
    expect(validateForm(filled({ name: '   ' }), undefined).name).toBe('Deal Name을 입력하세요.')
  })

  it.each(['0', '-5', '1.5', 'abc'])('rejects the amount %s', (text) => {
    expect(validateForm(filled({ revenueAmount: text }), undefined).revenueAmount).toBe('매출금액은 1원 이상의 정수로 입력하세요.')
  })

  it('rejects Users that is not a positive integer but allows it to be empty', () => {
    expect(validateForm(filled({ users: '0' }), undefined).users).toBe('Users는 1 이상의 정수로 입력하세요.')
    expect(validateForm(filled({ users: '2.5' }), undefined).users).toBe('Users는 1 이상의 정수로 입력하세요.')
    expect(validateForm(filled({ users: '' }), undefined).users).toBeUndefined()
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
    const resigned: UserRef = { id: 'u-old', name: '강퇴사', role: 'sales', status: 'resigned' }
    const errors = validateForm(filled({ ownerId: 'u-old' }), resigned)
    expect(errors.ownerId).toBe('퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.')
    expect(validateForm(filled({ ownerId: 'u-kim' }), resigned).ownerId).toBeUndefined()
  })
})

describe('toDealInput', () => {
  it('trims, converts numbers and uses null for empty optional values', () => {
    const input = toDealInput(
      filled({
        vendor: ' Okta ',
        users: '20',
        customer: { contactId: 'ct-1', company: '한빛은행', name: '정민수', title: ' 과장 ', email: '', phone: '' },
        quoteSubmitted: 'YES',
        quoteDate: '2026-10-01',
      }),
    )
    expect(input.name).toBe('새 Deal')
    expect(input.vendor).toBe('Okta')
    expect(input.users).toBe(20)
    expect(input.revenueAmount).toBe(1_500_000)
    expect(input.customer).toEqual({ contactId: 'ct-1', company: '한빛은행', name: '정민수', title: '과장', email: null, phone: null })
    expect(input.partner).toBeNull()
    expect(input.quote).toEqual({ submitted: 'YES', submittedDate: '2026-10-01' })
    expect(input.poc).toEqual({ state: null, completedDate: null })
  })

  it('sends the partner only when it was entered', () => {
    const input = toDealInput(filled({ partner: { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' } }))
    expect(input.partner).toMatchObject({ company: '코어테크', name: '민지훈', email: null })
  })
})

describe('formFromDeal / toDealPatch (T-FORM-06)', () => {
  it('loads every field of an existing deal', () => {
    const state = formFromDeal(detail())
    expect(state).toMatchObject({
      name: '기존 Deal',
      ownerId: 'u-kim',
      users: '100',
      statusKey: 'introduction',
      forecastKey: 'best',
      revenueAmount: '300000000',
      revenueDate: '2027-03-01',
      quoteSubmitted: 'YES',
      procurement: '검토',
    })
    expect(state.customer).toMatchObject({ contactId: 'ct-1', company: '한빛은행', name: '정민수', title: '과장' })
    expect(state.partner).toMatchObject({ contactId: 'ct-9', company: '에이원시스템', name: '표성호' })
    expect(state.bant.budget).toBe('lb-1')
  })

  it('removes the active partner when its fields are cleared', () => {
    const original = detail()
    const state = { ...formFromDeal(original), partner: EMPTY_DRAFT }
    expect(toDealPatch(state, original).partner).toBeNull()
  })

  it('leaves the partner out when there was none and none is entered', () => {
    const original = detail({ activePartner: null })
    expect('partner' in toDealPatch(formFromDeal(original), original)).toBe(false)
  })

  it('sends the replacement partner as a draft', () => {
    const original = detail()
    const state = { ...formFromDeal(original), partner: { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' } }
    expect(toDealPatch(state, original).partner).toMatchObject({ contactId: null, company: '코어테크' })
  })
})

describe('replacedPartner (T-FORM-05 notice)', () => {
  const original = detail()

  it('is the active partner when a different one is entered', () => {
    const draft = { ...EMPTY_DRAFT, company: '코어테크', name: '민지훈' }
    expect(replacedPartner(original, draft)?.name).toBe('표성호')
  })

  it('is null for the same contact, for an empty draft and when there was no partner', () => {
    const same = { ...EMPTY_DRAFT, contactId: 'ct-9', company: '에이원시스템', name: '표성호', title: '이사' }
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
