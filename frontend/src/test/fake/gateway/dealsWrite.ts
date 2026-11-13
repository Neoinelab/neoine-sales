/** Deal 쓰기: 등록·수정·단일 필드 변경·삭제. 검증과 연락처 계획을 모두 끝낸 뒤에만 저장소를 바꾼다. */

import { compactDate } from '../../../shared/model/dates'
import { businessToday } from '../businessDate'
import { FORECAST_WON } from '../../../shared/model/constants'
import { canWrite } from '../../../shared/model/permissions'
import type { Deal, DealInput, DealPatch } from '../../../shared/model/types'
import { WRITE_DENIED_MESSAGE, conflict, forbidden, requestValidation, validation } from '../errors'
import { requireUser, requireWrite, viewerOf, write, clone, type MockContext } from './context'
import { commitBant } from './bantChoice'
import { commitContact, planContact, type ContactPlan } from './contactPlan'
import { assertWonExitAllowed, followWonChange, removeContractsOfDeal } from './contractWon'
import { commitDealChange, planDealChange } from './dealChange'
import { providedKeys, validateCustomerDraft, validateDealFields, validatePartnerDraft } from './dealValidation'
import { logDealDiff, logHistory } from './historyLog'
import { dealDetail, findDeal } from './views'

const DELETE_OWNER_DENIED_MESSAGE = '본인 Deal 또는 admin만 삭제할 수 있습니다.'
const DELETE_COMPLETED_DENIED_MESSAGE = '완료된 Deal은 관리자만 삭제할 수 있습니다.'

const CODE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'

/** 서버와 같은 시도 횟수와 문구(DE-R2): 겹치면 다시 뽑고 10번째까지 시도한 뒤 409다. */
export const DEAL_CODE_ATTEMPTS = 10
export const DEAL_CODE_ISSUE_FAILED_MESSAGE = 'Deal code를 발급하지 못했습니다. 다시 시도하세요.'

/** `YYYYMMDD-XXXX`. 기존 code와 겹치면 다시 뽑고, 10번 모두 겹치면 409(conflict)다. */
export function newDealCode(ctx: MockContext): string {
  const prefix = compactDate(ctx.clock.today())
  const used = new Set(ctx.store.data.deals.map((d) => d.code))
  for (let attempt = 0; attempt < DEAL_CODE_ATTEMPTS; attempt += 1) {
    let suffix = ''
    for (let i = 0; i < 4; i += 1) suffix += CODE_CHARS[Math.floor(ctx.random() * CODE_CHARS.length)] ?? 'A'
    const code = `${prefix}-${suffix}`
    if (!used.has(code)) return code
  }
  throw conflict(DEAL_CODE_ISSUE_FAILED_MESSAGE)
}

function createDeal(ctx: MockContext, raw: DealInput) {
  const user = requireWrite(ctx)
  // 서버 요청 모델: Vendor 누락·null은 요청 형식 오류(422)이고, Solution은 생략·null이면 빈 문자열이다.
  if ((raw.vendorId as number | null | undefined) == null) throw requestValidation()
  const input: DealInput = { ...raw, solution: raw.solution ?? '' }
  const bantDraft = validateDealFields(ctx, input, () => true, input.bant)
  validateCustomerDraft(input.customer)
  if (input.partner) validatePartnerDraft(input.partner)
  const customerPlan = planContact(ctx, 'customer', input.customer)
  const partnerPlan = input.partner ? planContact(ctx, 'partner', input.partner) : null

  // 모든 검증이 끝난 뒤에만 연락처와 새 BANT Label을 만든다.
  const bant = commitBant(ctx, bantDraft ?? { chosen: { budget: null, authority: null, need: null, timeline: null }, newNames: {} }, user.id)
  const customerId = commitContact(ctx, customerPlan, user.id)
  const partnerId = partnerPlan ? commitContact(ctx, partnerPlan, user.id) : null
  const now = ctx.clock.now()
  const deal: Deal = {
    code: newDealCode(ctx),
    name: input.name.trim(),
    ownerId: input.ownerId,
    vendorId: input.vendorId,
    solution: input.solution.trim(),
    users: input.users,
    statusKey: input.statusKey,
    forecastKey: input.forecastKey,
    revenueAmount: input.revenueAmount,
    revenueDate: input.revenueDate,
    customerContactId: customerId,
    partnerLinks: partnerId ? [{ contactId: partnerId, active: true, linkedAt: now, unlinkedAt: null }] : [],
    quote: clone(input.quote),
    poc: clone(input.poc),
    procurement: input.procurement.trim(),
    bant,
    statusChangedOn: businessToday(now),
    createdAt: now,
    updatedAt: now,
  }
  ctx.store.data.deals.push(deal)
  logHistory(ctx, deal.code, user.id, 'created', 'Deal 등록', '', 'Deal 등록')
  followWonChange(ctx, deal.code, null, deal, false, user.id)
  return dealDetail(ctx, deal)
}

const SCALAR_KEYS = [
  'name', 'ownerId', 'vendorId', 'solution', 'users', 'statusKey', 'forecastKey',
  'revenueAmount', 'revenueDate', 'quote', 'poc', 'procurement',
] as const satisfies readonly (keyof DealPatch)[]

function updateDeal(ctx: MockContext, code: string, patch: DealPatch) {
  const user = requireWrite(ctx)
  const deal = findDeal(ctx.store.data, code)
  const provided = providedKeys(patch)
  const after: Deal = { ...clone(deal) }
  for (const key of SCALAR_KEYS) {
    if (patch[key] !== undefined) Object.assign(after, { [key]: clone(patch[key]) })
  }
  if (typeof patch.name === 'string') after.name = patch.name.trim()
  if (typeof patch.procurement === 'string') after.procurement = patch.procurement.trim()
  if (typeof patch.solution === 'string') after.solution = patch.solution.trim()
  const bantDraft = validateDealFields(ctx, after, provided, patch.bant)

  let customerPlan: ContactPlan | null = null
  let partnerPlan: ContactPlan | null = null
  if (patch.customer) {
    validateCustomerDraft(patch.customer)
    customerPlan = planContact(ctx, 'customer', patch.customer)
  }
  if (patch.partner) {
    validatePartnerDraft(patch.partner)
    partnerPlan = planContact(ctx, 'partner', patch.partner)
  }

  assertWonExitAllowed(ctx.store.data, code, deal, after)
  const before = clone(deal)
  const now = ctx.clock.now()
  if (bantDraft) after.bant = commitBant(ctx, bantDraft, user.id)
  if (customerPlan) after.customerContactId = commitContact(ctx, customerPlan, user.id)
  if (patch.partner === null || partnerPlan) {
    const partnerId = partnerPlan ? commitContact(ctx, partnerPlan, user.id) : null
    const active = after.partnerLinks.find((l) => l.active)
    if (active?.contactId !== partnerId) {
      if (active) Object.assign(active, { active: false, unlinkedAt: now })
      if (partnerId) after.partnerLinks.push({ contactId: partnerId, active: true, linkedAt: now, unlinkedAt: null })
    }
  }
  // 연락처 갱신이 이 Deal의 updatedAt을 이미 올렸을 수 있으므로 저장소 값을 이어받는다.
  after.updatedAt = deal.updatedAt
  Object.assign(deal, after)
  if (deal.statusKey !== before.statusKey) deal.statusChangedOn = businessToday(now)
  if (logDealDiff(ctx, before, deal, user.id) > 0) deal.updatedAt = now
  followWonChange(ctx, deal.code, before, deal, patch.deleteLicenseContracts, user.id)
  return dealDetail(ctx, deal)
}

export function dealsWriteApi(ctx: MockContext) {
  return {
    create: (input: DealInput) => write(ctx, () => createDeal(ctx, input)),
    update: (code: string, patch: DealPatch) => write(ctx, () => updateDeal(ctx, code, patch)),
    applyChange: (code: string, request: Parameters<typeof planDealChange>[2]) =>
      write(ctx, () => {
        const user = requireWrite(ctx)
        const deal = findDeal(ctx.store.data, code)
        const outcome = planDealChange(ctx, deal, request)
        const before = { statusKey: deal.statusKey, forecastKey: deal.forecastKey }
        assertWonExitAllowed(ctx.store.data, code, before, { ...before, ...outcome.patch })
        commitDealChange(ctx, deal, outcome, user.id)
        followWonChange(ctx, code, before, deal, request.deleteLicenseContracts, user.id)
        return { deal: dealDetail(ctx, deal), coChanged: outcome.coChanged, notice: outcome.notice }
      }),
    remove: (code: string, confirmCode: string) =>
      write(ctx, () => {
        const user = requireUser(ctx)
        // 서버: 역할 가드가 먼저라 user는 Deal 존재와 무관하게 읽기 전용 문구의 403이다.
        if (!canWrite(user.role)) throw forbidden(WRITE_DENIED_MESSAGE)
        const { data } = ctx.store
        const deal = findDeal(data, code)
        // 서버 DD-R24 순서: Owner·admin 판정 → 완료된 Deal(Forecast won)은 admin만 → 확인 code. 화면 판정(permissions)과 별개로 서버를 그대로 따른다.
        const viewer = viewerOf(user)
        if (!(viewer.role === 'admin' || (viewer.role === 'sales' && viewer.id === deal.ownerId))) throw forbidden(DELETE_OWNER_DENIED_MESSAGE)
        if (deal.forecastKey === FORECAST_WON && viewer.role !== 'admin') throw forbidden(DELETE_COMPLETED_DENIED_MESSAGE)
        if (confirmCode !== code) throw validation('Deal code가 일치하지 않습니다.')
        data.deals.splice(data.deals.indexOf(deal), 1)
        data.history = data.history.filter((h) => h.dealCode !== code)
        data.actions = data.actions.filter((a) => a.dealCode !== code)
        data.attachments = data.attachments.filter((a) => a.dealCode !== code)
        removeContractsOfDeal(data, code)
      }),
  }
}
