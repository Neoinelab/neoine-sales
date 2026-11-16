/** Deal 등록·수정 입력 검증(서버 규칙). 첫 오류에서 ApiError(422)를 던진다. */

import { isValidAmount } from '../../../shared/model/money'
import { canBeOwner } from '../../../shared/model/permissions'
import { isSyncConsistent } from '../../../shared/model/sync'
import type { ContactDraft, Deal, DealInput } from '../../../shared/model/types'
import { validation } from '../errors'
import { checkBant, type BantChoices, type BantDraft } from './bantChoice'
import type { MockContext } from './context'
import { UNKNOWN_VENDOR_MESSAGE } from './vendors'

export const SYNC_MISMATCH_MESSAGE = 'Status와 Forecast의 동기화가 맞지 않습니다.'
export const PARTNER_INCOMPLETE_MESSAGE = '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.'

/** 서버 문구: 수정에서 Vendor를 null로 보낸 경우(등록의 누락·null은 요청 형식 오류다). */
export const VENDOR_REQUIRED_MESSAGE = 'Vendor를 선택하세요.'
export const PRODUCT_TOO_LONG_MESSAGE = 'Product는 200자 이내로 입력하세요.'

/** 서버 값 규칙(Deal Name 200자, Product 200자, 구매절차 500자, Users count는 DB 정수 상한). */
const NAME_MAX = 200
const PRODUCT_MAX = 200
const PROCUREMENT_MAX = 500
const USERS_MAX = 2_147_483_647

type Scalars = Pick<
  Deal,
  'name' | 'vendorId' | 'product' | 'ownerId' | 'users' | 'procurement' | 'statusKey' | 'forecastKey' | 'revenueAmount' | 'revenueDate'
>

/** 선택 필드를 쓰지 않으면 `provided('bant')`가 false인 입력(등록은 항상 true). */
export type ProvidedKeys = (key: keyof Scalars | 'bant') => boolean

/** 서버와 같은 NUL 문자 거절 문구(PL-R16): 텍스트는 공백으로 감싸도 NUL이 있으면 거절한다. */
const nulMessage = (column: string): string => `${column}에는 NUL 문자를 쓸 수 없습니다`

/** Vendor 선택 검증(서버와 같은 순서: Deal Name 다음, Product 앞). Vendor는 필수라 null은 거절한다. Product는 Vendor와 무관한 텍스트다. */
function validateVendorChoice(ctx: MockContext, effective: Scalars, check: boolean): void {
  if (!check) return
  if (effective.vendorId === null || effective.vendorId === undefined) throw validation(VENDOR_REQUIRED_MESSAGE)
  if (!ctx.store.data.vendors.some((v) => v.id === effective.vendorId)) {
    throw validation(UNKNOWN_VENDOR_MESSAGE)
  }
}

/** Product 텍스트 검증(선택: 앞뒤 공백을 지운 뒤 0~200자, NUL 거부). 빈 값은 오류가 아니다. */
function validateProduct(effective: Scalars, check: boolean): void {
  if (!check) return
  if (effective.product.includes('\u0000')) throw validation(nulMessage('Product'))
  if (Array.from(effective.product.trim()).length > PRODUCT_MAX) throw validation(PRODUCT_TOO_LONG_MESSAGE)
}

/**
 * `provided(key)`가 true인 필드만 검사한다(등록은 모두, 수정은 보낸 필드만). `effective`는 반영 후 값.
 * BANT는 선택 객체(`bant`)를 판정만 하고(검증 순서: 동기화 다음, 구매절차 앞) 결과를 돌려준다.
 * 새 Label 생성은 호출자가 모든 검증을 마친 뒤 `commitBant`로 한다.
 */
export function validateDealFields(
  ctx: MockContext,
  effective: Scalars,
  provided: ProvidedKeys,
  bant: BantChoices | undefined,
): BantDraft | null {
  const { data } = ctx.store
  if (provided('name') && effective.name.includes('\u0000')) throw validation(nulMessage('Deal Name'))
  if (provided('name') && effective.name.trim() === '') throw validation('Deal Name을 입력하세요.')
  if (provided('name') && Array.from(effective.name.trim()).length > NAME_MAX) throw validation('Deal Name은 200자 이내로 입력하세요.')
  validateVendorChoice(ctx, effective, provided('vendorId'))
  validateProduct(effective, provided('product'))
  if (provided('ownerId')) {
    const owner = data.users.find((u) => u.id === effective.ownerId)
    if (owner?.status === 'resigned') throw validation('퇴사한 사용자는 Owner로 지정할 수 없습니다. 다른 담당자를 선택하세요.')
    if (!owner || !canBeOwner(owner)) throw validation('Owner는 재직 중인 영업 담당자여야 합니다.')
  }
  if (provided('revenueAmount') && !isValidAmount(effective.revenueAmount)) {
    throw validation('매출금액은 1원 이상의 정수로 입력하세요.')
  }
  if (provided('revenueDate') && !/^\d{4}-\d{2}-\d{2}$/.test(effective.revenueDate)) {
    throw validation('Expected Close를 입력하세요.')
  }
  if (provided('users')) {
    const users: unknown = effective.users
    if (users === null || users === undefined) throw validation('Users count를 입력하세요.')
    if (typeof users !== 'number' || !Number.isInteger(users) || users < 0 || users > USERS_MAX) {
      throw validation('Users count는 0 이상의 정수로 입력하세요.')
    }
  }
  if (provided('statusKey') && !data.codes.some((c) => c.kind === 'status' && c.key === effective.statusKey)) {
    throw validation('Status를 선택하세요.')
  }
  if (provided('forecastKey') && !data.codes.some((c) => c.kind === 'forecast' && c.key === effective.forecastKey)) {
    throw validation('Forecast를 선택하세요.')
  }
  if ((provided('statusKey') || provided('forecastKey')) && !isSyncConsistent(effective)) {
    throw validation(SYNC_MISMATCH_MESSAGE)
  }
  const draft = provided('bant') ? checkBant(ctx, bant ?? {}) : null
  if (provided('procurement') && effective.procurement.includes('\u0000')) throw validation(nulMessage('구매절차'))
  if (provided('procurement') && Array.from(effective.procurement.trim()).length > PROCUREMENT_MAX) {
    throw validation('구매절차는 500자 이내로 입력하세요.')
  }
  return draft
}

/** 고객 연락처 필수 입력 확인(Deal 폼 문구). */
export function validateCustomerDraft(draft: ContactDraft): void {
  if (draft.company === '') throw validation('고객 회사명을 입력하세요.')
  if (draft.name === '') throw validation('고객 담당자명을 입력하세요.')
}

/** 파트너를 입력했다면 회사명과 담당자명이 모두 필요하다. */
export function validatePartnerDraft(draft: ContactDraft): void {
  if (draft.company === '' || draft.name === '') throw validation(PARTNER_INCOMPLETE_MESSAGE)
}

export function providedKeys(input: Partial<DealInput>): (key: string) => boolean {
  return (key) => (input as Record<string, unknown>)[key] !== undefined
}
