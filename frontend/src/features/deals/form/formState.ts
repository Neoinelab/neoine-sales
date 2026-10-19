import { FORECAST_PIPELINE, STATUS_PROSPECTING } from '../../../shared/model/constants'
import { validateContactInput, type ContactFieldErrors } from '../../../shared/model/contactRules'
import type { ContactDraft } from '../../../shared/model/inputs'
import { parseAmount } from '../../../shared/model/money'
import type {
  BantSelection,
  Contact,
  DealDetail,
  DealInput,
  DealPatch,
  PocState,
  QuoteSubmitted,
  UserRef,
} from '../../../shared/model/types'

export const OWNER_RESIGNED_MESSAGE = '퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.'
export const PARTNER_INCOMPLETE_MESSAGE = '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.'

export const EMPTY_DRAFT: ContactDraft = { contactId: null, company: '', name: '', title: '', email: null, phone: null }

/** 입력란에 그대로 묶이는 폼 상태. 숫자·날짜도 문자열로 들고 있다가 저장할 때 변환한다. */
export interface DealFormState {
  name: string
  ownerId: string
  /** Vendor/Solution id. 빈 문자열은 선택 안 함. */
  vendorId: string
  solutionId: string
  users: string
  statusKey: string
  forecastKey: string
  revenueAmount: string
  revenueDate: string
  customer: ContactDraft
  partner: ContactDraft
  bant: BantSelection
  quoteSubmitted: '' | QuoteSubmitted
  quoteDate: string
  pocState: '' | PocState
  pocDate: string
  procurement: string
}

export interface FormErrors {
  name?: string
  ownerId?: string
  users?: string
  revenueAmount?: string
  revenueDate?: string
  customer?: ContactFieldErrors
  partner?: ContactFieldErrors
}

export function emptyForm(ownerId: string): DealFormState {
  return {
    name: '',
    ownerId,
    vendorId: '',
    solutionId: '',
    users: '',
    statusKey: STATUS_PROSPECTING,
    forecastKey: FORECAST_PIPELINE,
    revenueAmount: '',
    revenueDate: '',
    customer: EMPTY_DRAFT,
    partner: EMPTY_DRAFT,
    bant: { budget: null, authority: null, need: null, timeline: null },
    quoteSubmitted: '',
    quoteDate: '',
    pocState: '',
    pocDate: '',
    procurement: '',
  }
}

function draftOf(contact: Contact): ContactDraft {
  return {
    contactId: contact.id,
    company: contact.company,
    name: contact.name,
    title: contact.title,
    email: contact.email,
    phone: contact.phone,
  }
}

export function formFromDeal(deal: DealDetail): DealFormState {
  return {
    name: deal.name,
    ownerId: deal.ownerId,
    vendorId: deal.vendor?.id ?? '',
    solutionId: deal.solution?.id ?? '',
    users: deal.users === null ? '' : String(deal.users),
    statusKey: deal.statusKey,
    forecastKey: deal.forecastKey,
    revenueAmount: String(deal.revenueAmount),
    revenueDate: deal.revenueDate,
    customer: draftOf(deal.customer),
    partner: deal.activePartner ? draftOf(deal.activePartner) : EMPTY_DRAFT,
    bant: { ...deal.bant },
    quoteSubmitted: deal.quote.submitted ?? '',
    quoteDate: deal.quote.submittedDate ?? '',
    pocState: deal.poc.state ?? '',
    pocDate: deal.poc.completedDate ?? '',
    procurement: deal.procurement,
  }
}

/** 파트너 영역에 무언가 입력했는가(입력을 시작하면 회사명·담당자명이 필수). */
export function isPartnerEntered(draft: ContactDraft): boolean {
  return [draft.company, draft.name, draft.title, draft.email ?? '', draft.phone ?? ''].some((text) => text.trim() !== '')
}

export function hasErrors(errors: FormErrors): boolean {
  return Object.values(errors).some((value) => value !== undefined)
}

function nonEmpty(errors: ContactFieldErrors): ContactFieldErrors | undefined {
  return Object.keys(errors).length > 0 ? errors : undefined
}

/** 필수 문구는 Deal 폼 자체 문구를 쓰고, 공백·형식 오류는 연락처 규칙을 따른다. */
function customerErrors(draft: ContactDraft): ContactFieldErrors | undefined {
  const errors = validateContactInput(draft)
  if (draft.company === '') errors.company = '고객 회사명을 입력하세요.'
  if (draft.name === '') errors.name = '고객 담당자명을 입력하세요.'
  return nonEmpty(errors)
}

function partnerErrors(draft: ContactDraft): ContactFieldErrors | undefined {
  if (!isPartnerEntered(draft)) return undefined
  const errors = validateContactInput(draft)
  delete errors.company
  delete errors.name
  if (draft.company === '' || draft.name === '') errors.company = PARTNER_INCOMPLETE_MESSAGE
  return nonEmpty(errors)
}

/** 화면 위에서 아래 순서의 필수·형식 검증. `originalOwner`는 수정 중인 Deal의 현재 Owner. */
export function validateForm(state: DealFormState, originalOwner: UserRef | undefined): FormErrors {
  const errors: FormErrors = {}
  if (state.name.trim() === '') errors.name = 'Deal Name을 입력하세요.'
  if (state.ownerId === '') errors.ownerId = 'Owner를 선택하세요.'
  else if (originalOwner?.status === 'resigned' && originalOwner.id === state.ownerId) errors.ownerId = OWNER_RESIGNED_MESSAGE
  const users = state.users.trim()
  if (users !== '' && !(/^\d+$/.test(users) && Number(users) >= 1)) errors.users = 'Users는 1 이상의 정수로 입력하세요.'
  const customer = customerErrors(state.customer)
  if (customer) errors.customer = customer
  const partner = partnerErrors(state.partner)
  if (partner) errors.partner = partner
  if (parseAmount(state.revenueAmount) === null) errors.revenueAmount = '매출금액은 1원 이상의 정수로 입력하세요.'
  if (state.revenueDate === '') errors.revenueDate = 'Expected Close를 입력하세요.'
  return errors
}

function normalize(draft: ContactDraft): ContactDraft {
  return {
    contactId: draft.contactId,
    company: draft.company,
    name: draft.name,
    title: draft.title.trim(),
    email: draft.email?.trim() || null,
    phone: draft.phone?.trim() || null,
  }
}

/** 검증을 통과한 상태를 게이트웨이 입력으로 바꾼다. */
export function toDealInput(state: DealFormState): DealInput {
  const users = state.users.trim()
  return {
    name: state.name.trim(),
    ownerId: state.ownerId,
    vendorId: state.vendorId || null,
    solutionId: state.solutionId || null,
    users: users === '' ? null : Number(users),
    statusKey: state.statusKey,
    forecastKey: state.forecastKey,
    revenueAmount: parseAmount(state.revenueAmount) ?? 0,
    revenueDate: state.revenueDate,
    customer: normalize(state.customer),
    partner: isPartnerEntered(state.partner) ? normalize(state.partner) : null,
    quote: { submitted: state.quoteSubmitted || null, submittedDate: state.quoteDate || null },
    poc: { state: state.pocState || null, completedDate: state.pocDate || null },
    procurement: state.procurement.trim(),
    bant: { ...state.bant },
  }
}

/** 수정 저장 입력. 활성 파트너가 있었는데 비웠으면 `partner: null`(제거), 원래 없고 비었으면 파트너 키를 보내지 않는다. */
export function toDealPatch(state: DealFormState, original: DealDetail): DealPatch {
  const { partner, ...rest } = toDealInput(state)
  const patch: DealPatch = rest
  if (partner) patch.partner = partner
  else if (original.activePartner) patch.partner = null
  return patch
}

/** 입력한 파트너가 현재 활성 파트너와 다른 사람이면 그 활성 파트너(교체되어 비활성이 될 대상), 아니면 null. */
export function replacedPartner(original: DealDetail | undefined, draft: ContactDraft): Contact | null {
  const active = original?.activePartner
  if (!active || !isPartnerEntered(draft)) return null
  if (draft.contactId === active.id) return null
  const same =
    draft.contactId === null &&
    draft.company.toLowerCase() === active.company.toLowerCase() &&
    draft.name.toLowerCase() === active.name.toLowerCase()
  return same ? null : active
}
