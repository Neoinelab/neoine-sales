/** Deal 등록·수정 입력 검증(서버 규칙). 첫 오류에서 ApiError(422)를 던진다. */

import { isValidAmount } from '../../../shared/model/money'
import { canBeOwner } from '../../../shared/model/permissions'
import { isSyncConsistent } from '../../../shared/model/sync'
import type { ContactDraft, Deal, DealInput } from '../../../shared/model/types'
import { validation } from '../errors'
import { checkBant, type BantChoices, type BantDraft } from './bantChoice'
import type { MockContext } from './context'
import { SOLUTION_MISMATCH_MESSAGE, SOLUTION_NEEDS_VENDOR_MESSAGE, UNKNOWN_VENDOR_MESSAGE } from './vendors'

export const SYNC_MISMATCH_MESSAGE = 'Status와 Forecast의 동기화가 맞지 않습니다.'
export const PARTNER_INCOMPLETE_MESSAGE = '파트너를 입력하면 회사명과 담당자명이 모두 필요합니다.'

/** 서버 값 규칙(Deal Name 200자, 구매절차 500자, Users는 DB 정수 상한). */
const NAME_MAX = 200
const PROCUREMENT_MAX = 500
const USERS_MAX = 2_147_483_647

type Scalars = Pick<
  Deal,
  'name' | 'vendorId' | 'solutionId' | 'ownerId' | 'users' | 'procurement' | 'statusKey' | 'forecastKey' | 'revenueAmount' | 'revenueDate'
>

/** 선택 필드를 쓰지 않으면 `provided('bant')`가 false인 입력(등록은 항상 true). */
export type ProvidedKeys = (key: keyof Scalars | 'bant') => boolean

/** Vendor·Solution 선택 검증(서버와 같은 순서: Deal Name 다음, Owner 앞). */
function validateVendorChoice(ctx: MockContext, effective: Scalars, check: boolean): void {
  const { vendors, solutions } = ctx.store.data
  if (effective.solutionId !== null && effective.vendorId === null) throw validation(SOLUTION_NEEDS_VENDOR_MESSAGE)
  if (!check) return
  if (effective.vendorId !== null && !vendors.some((v) => v.id === effective.vendorId)) throw validation(UNKNOWN_VENDOR_MESSAGE)
  if (effective.solutionId !== null && !solutions.some((s) => s.id === effective.solutionId && s.vendorId === effective.vendorId)) {
    throw validation(SOLUTION_MISMATCH_MESSAGE)
  }
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
  if (provided('name') && effective.name.trim() === '') throw validation('Deal Name을 입력하세요.')
  if (provided('name') && Array.from(effective.name.trim()).length > NAME_MAX) throw validation('Deal Name은 200자 이내로 입력하세요.')
  validateVendorChoice(ctx, effective, provided('vendorId') || provided('solutionId'))
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
    if (users === null || users === undefined) throw validation('Users를 입력하세요.')
    if (typeof users !== 'number' || !Number.isInteger(users) || users < 0 || users > USERS_MAX) {
      throw validation('Users는 0 이상의 정수로 입력하세요.')
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
