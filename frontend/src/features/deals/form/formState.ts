import { toChoice } from '../../../shared/model/catalogChoice'
import {
  BANT_CATEGORIES,
  BANT_LABEL_MAX_LENGTH,
  FORECAST_PIPELINE,
  STATUS_PROSPECTING,
  type BantCategory,
} from '../../../shared/model/constants'
import { validateContactInput, type ContactFieldErrors } from '../../../shared/model/contactRules'
import { parseId } from '../../../shared/model/ids'
import type { ContactDraft } from '../../../shared/model/inputs'
import { amountInputError, formatThousandWon, isSameShownAmount, parseAmountInput } from '../../../shared/model/money'
import type {
  BantLabel,
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
export const USERS_REQUIRED_MESSAGE = 'Users를 입력하세요.'
export const USERS_MESSAGE = 'Users는 0 이상의 정수로 입력하세요.'

export const EMPTY_DRAFT: ContactDraft = { contactId: null, company: '', name: '', title: '', email: null, phone: null }

/** 입력란에 그대로 묶이는 폼 상태. 숫자·날짜도 문자열로 들고 있다가 저장할 때 변환한다. */
export interface DealFormState {
  name: string
  ownerId: string
  /** Owner·Vendor·Solution id는 select 값(10진 문자열)으로 들고, 저장할 때 `parseId`로 정수로 바꾼다. 빈 문자열은 선택 안 함. */
  vendorId: string
  solutionId: string
  users: string
  statusKey: string
  forecastKey: string
  revenueAmount: string
  revenueDate: string
  customer: ContactDraft
  partner: ContactDraft
  /** 구분별 Label 이름 텍스트(자동완성 입력). 비면 선택 안 함. */
  bant: Record<BantCategory, string>
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
  bant?: Partial<Record<BantCategory, string>>
}

export const BANT_TOO_LONG_MESSAGE = `Label 이름은 ${BANT_LABEL_MAX_LENGTH}자 이내로 입력하세요.`

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
    bant: { budget: '', authority: '', need: '', timeline: '' },
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

/** 구분별 Label 목록. */
const labelsOf = (labels: readonly BantLabel[], category: BantCategory) => labels.filter((l) => l.category === category)

/** 수정 폼의 BANT 초기 텍스트: 현재 Label 이름(목록에서 못 찾거나 선택 안 함이면 빈 칸). */
export function bantTexts(bant: DealDetail['bant'], labels: readonly BantLabel[]): Record<BantCategory, string> {
  const nameOf = (category: BantCategory) => labelsOf(labels, category).find((l) => l.id === bant[category])?.name ?? ''
  return { budget: nameOf('budget'), authority: nameOf('authority'), need: nameOf('need'), timeline: nameOf('timeline') }
}

export function formFromDeal(deal: DealDetail, labels: readonly BantLabel[]): DealFormState {
  return {
    name: deal.name,
    ownerId: String(deal.ownerId),
    vendorId: deal.vendor ? String(deal.vendor.id) : '',
    solutionId: deal.solution ? String(deal.solution.id) : '',
    users: String(deal.users),
    statusKey: deal.statusKey,
    forecastKey: deal.forecastKey,
    revenueAmount: formatThousandWon(deal.revenueAmount),
    revenueDate: deal.revenueDate,
    customer: draftOf(deal.customer),
    partner: deal.activePartner ? draftOf(deal.activePartner) : EMPTY_DRAFT,
    bant: bantTexts(deal.bant, labels),
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

/** 50자(코드 포인트) 초과 항목만 표시한다. 그 밖의 검증은 서버가 한다. */
function bantErrors(texts: Record<BantCategory, string>): FormErrors['bant'] {
  const errors: NonNullable<FormErrors['bant']> = {}
  for (const category of BANT_CATEGORIES) {
    if ([...texts[category].trim()].length > BANT_LABEL_MAX_LENGTH) errors[category] = BANT_TOO_LONG_MESSAGE
  }
  return Object.keys(errors).length > 0 ? errors : undefined
}

/** 화면 위에서 아래 순서의 필수·형식 검증. `originalOwner`는 수정 중인 Deal의 현재 Owner. */
export function validateForm(
  state: DealFormState,
  originalOwner: UserRef | undefined,
  originalAmount?: number,
): FormErrors {
  const errors: FormErrors = {}
  if (state.name.trim() === '') errors.name = 'Deal Name을 입력하세요.'
  if (parseId(state.ownerId) === undefined) errors.ownerId = 'Owner를 선택하세요.'
  else if (originalOwner?.status === 'resigned' && String(originalOwner.id) === state.ownerId) errors.ownerId = OWNER_RESIGNED_MESSAGE
  const users = state.users.trim()
  if (users === '') errors.users = USERS_REQUIRED_MESSAGE
  else if (!/^\d+$/.test(users)) errors.users = USERS_MESSAGE
  const customer = customerErrors(state.customer)
  if (customer) errors.customer = customer
  const partner = partnerErrors(state.partner)
  if (partner) errors.partner = partner
  // 금액을 건드리지 않았으면(표시값 그대로) 검증하지 않는다. 1~499원 Deal은 표시가 0이다.
  const untouched = originalAmount !== undefined && state.revenueAmount === formatThousandWon(originalAmount)
  const amountError = untouched ? null : amountInputError(state.revenueAmount)
  if (amountError !== null) errors.revenueAmount = amountError
  if (state.revenueDate === '') errors.revenueDate = 'Expected Close를 입력하세요.'
  const bant = bantErrors(state.bant)
  if (bant) errors.bant = bant
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
export function toDealInput(state: DealFormState, labels: readonly BantLabel[]): DealInput {
  const users = state.users.trim()
  const ownerId = parseId(state.ownerId)
  if (ownerId === undefined) throw new Error('Owner를 선택하세요.')
  return {
    name: state.name.trim(),
    ownerId,
    vendorId: parseId(state.vendorId) ?? null,
    solutionId: parseId(state.solutionId) ?? null,
    users: Number(users),
    statusKey: state.statusKey,
    forecastKey: state.forecastKey,
    revenueAmount: parseAmountInput(state.revenueAmount) ?? 0,
    revenueDate: state.revenueDate,
    customer: normalize(state.customer),
    partner: isPartnerEntered(state.partner) ? normalize(state.partner) : null,
    quote: { submitted: state.quoteSubmitted || null, submittedDate: state.quoteDate || null },
    poc: { state: state.pocState || null, completedDate: state.pocDate || null },
    procurement: state.procurement.trim(),
    bant: toBantChoices(state.bant, labels),
  }
}

/** 입력 텍스트를 구분 안의 Label과 견줘 `{id}`/`{name}`/null로 바꾼다. */
function toBantChoices(texts: Record<BantCategory, string>, labels: readonly BantLabel[]): DealInput['bant'] {
  const choice = (category: BantCategory) => toChoice(texts[category], labelsOf(labels, category))
  return { budget: choice('budget'), authority: choice('authority'), need: choice('need'), timeline: choice('timeline') }
}

/** 입력 텍스트가 처음(현재 Label 이름) 그대로인 구분은 이름을 다시 해석하지 않고 원래 `{id}`(없으면 null)를 보낸다. */
function keepUntouchedBant(bant: DealInput['bant'], state: DealFormState, original: DealDetail, labels: readonly BantLabel[]): DealInput['bant'] {
  const shown = bantTexts(original.bant, labels)
  const pick = (category: BantCategory) => {
    if (state.bant[category] !== shown[category]) return bant[category]
    const id = original.bant[category]
    return id ? { id } : null
  }
  return { budget: pick('budget'), authority: pick('authority'), need: pick('need'), timeline: pick('timeline') }
}

/** 수정 저장 입력. 활성 파트너가 있었는데 비웠으면 `partner: null`(제거), 원래 없고 비었으면 파트너 키를 보내지 않는다. */
export function toDealPatch(state: DealFormState, original: DealDetail, labels: readonly BantLabel[]): DealPatch {
  const { partner, ...rest } = toDealInput(state, labels)
  const patch: DealPatch = { ...rest, bant: keepUntouchedBant(rest.bant, state, original, labels) }
  // 표기상 같은 금액이면 원래 원 값을 유지한다(1000원 미만 끝자리 보존).
  // 텍스트가 원래 금액의 표기 그대로면 파싱하지 않는다(상한 근처 값은 파싱이 실패해 0이 된다).
  if (state.revenueAmount === formatThousandWon(original.revenueAmount) || isSameShownAmount(rest.revenueAmount, original.revenueAmount)) {
    patch.revenueAmount = original.revenueAmount
  }
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
